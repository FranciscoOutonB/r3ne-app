# Mesh import: making models R3NE loads well

Load this before you create or import an external model.

## What the Mesh Loader 3D actually does

`meshLoader3d` (`R3Ne/Scene3D/Nodes/MeshLoader3DNode.swift`):

| Path | Formats | Materials |
|---|---|---|
| Assimp | glb, gltf, fbx, obj(+mtl), dae, 3ds, blend, … | glTF: full metallic-roughness. Legacy diffuse/specular → approximated PBR |
| ModelIO (fallback) | usd/usda/usdc/usdz, ply, stl, abc | ModelIO / USD material properties |

On load, the loader:
- **Bakes node transforms into the vertices** (`PreTransformVertices`). Un-applied Blender transforms still land in the right place, but animation, skinning and morph targets are lost (it uses the static bind pose) and the hierarchy is flattened.
- **Merges meshes that share a material into one part.** Each part is one draw with its own material, named after one of its meshes (in the test, 4 crystals became the part "Crystal_3").
- **Reads** per vertex: position, normal, UV0. Tangents are generated. Per material: base color + texture, metallic/roughness (glTF packed G = roughness, B = metallic), normal map + scale, occlusion, emissive color × `KHR_materials_emissive_strength`, alpha mode + cutoff, doubleSided, clearcoat, sheen.
- **Ignores** vertex colors, UV1+, `KHR_texture_transform`, transmission, IOR and volume (glass), lights, cameras, animation.

Loader params (`import_mesh` sets them): `filePath` (absolute), `scale` (a port: uniform, baked into the vertices, so bounds include it), `zUp` (rotates Z-up sources to Y-up), `recenter` (moves the bbox centre to the origin), `useFileMaterials` (off uses the `albedoColor` port).

A connected Material node (`material3d`, presets, `pbrMaterial`) **replaces every part's material**.

## Format choice

1. **.glb (glTF binary)**: always prefer it. One file, embedded textures, correct PBR, meters and Y-up by spec.
2. .gltf + .bin + textures: fine, but keep the files together. The paths are relative to the .gltf.
3. .fbx: often centimeters (scale 0.01) and sometimes Z-up (`zUp: true`). Materials are approximate. Convert to .glb through Blender when it matters.
4. .obj + .mtl: no real PBR, textures only via the MTL. Fine for clay or override-material use.
5. .usdz: OK (ModelIO). .blend directly: unreliable (Assimp only reads old .blend versions), so export .glb from Blender instead.

## Asset checklist (author side)

- **Units:** meters. A person is ~1.75, a table ~0.75, a stage ~10–20. Check `boundsSize` after import.
- **Up axis:** +Y in glTF. Blender's exporter converts from Z-up (`export_yup=True`). Never rotate in R3NE to fix a bad export; re-export instead.
- **Apply transforms:** apply rotation and scale in Blender (`transform_apply`). Then set the **origin at the bottom centre** for props that sit on the ground, so `positionY 0` puts them on the floor and rotation pivots around the base. Use the geometric centre for floating or orbiting objects. The template script does this.
- **Normals:** export normals (`export_normals=True`). Use flat shading for the low-poly look, and smooth or auto-smooth for organic shapes. No normals → Assimp generates smooth ones. Watch for flipped faces (they render inside-out or vanish from one side): recalculate them outside in Blender.
- **Triangulation:** optional. Assimp triangulates. Pre-triangulate only if you need deterministic diagonals (terrain, deformed quads).
- **UVs:** UV0 is needed for any texture (and for tangents / normal maps). Unwrap or project. Keep the texel density consistent.
- **Materials:** one **Principled BSDF** per material, driven only by values or **Image Texture** nodes. The glTF exporter maps Base Color, Metallic, Roughness, Normal Map, Emission Color × Strength, Alpha, and AO (glTF settings node). Procedural nodes (Noise, Voronoi, ColorRamp, Mix) are **not exported**: bake them to images first, or use a `material3d` in R3NE with triplanar on.
- **Textures:** ≤ 2048 px (1024 for props, 512 for small or distant ones), power of two, PNG for masks/normals, JPEG for big color maps. Packed into the .glb. Albedo is sRGB, data maps (normal/roughness/metal/AO) are linear. R3NE builds mipmaps.
- **Emission:** keep Emission Strength around 1–3 for a saturated glow under AgX Punchy. 4+ reads as white in the core. Bloom does the rest.
- **Glass and transparency:** transmission/IOR aren't imported. Put glass parts in their own file and connect a `material3d` with `preset: "Glass"` (or transmission 1, ior 1.5, roughness ~0.02) plus Scene 3D `rtMode 1` (Hybrid) for real refraction. Alpha-blended surfaces (alphaMode BLEND) do import.
- **Naming:** name objects and materials meaningfully ("Rock", "Crystal", "GoldBand"). The part names in `import_mesh`'s report come from them.
- **No vertex colors:** R3NE ignores them. Bake to a texture, or split into materials (a small palette of materials is cheap and low-poly friendly).
- **Clean exports:** no cameras, lights, animation or hidden helper objects (`export_cameras/lights/animations=False`).

## One file per asset vs. one file per scene

- **One file per asset** (rock.glb, lamp.glb, chair.glb) is the default. You can transform each piece independently (each is its own Mesh Loader node with position/rotation), override its material, instance it, and reuse it across scenes.
- **One file for a static set** (a whole stage or room baked in place) is fine when nothing moves on its own. It's one loader, and the parts keep their materials. You can't move a sub-object or give it a different material later.
- Anything that needs a different R3NE material (glass, a video screen, an emissive/LED area driven by audio) → its own file.

## Repetition, LOD and instancing

- Repeating an object: **one** Mesh Loader → `instancer3d.geometry` → `scene.geo_N`. Don't create N loaders.
  - `mode` 0 Linear (`offsetX/Y/Z` per copy), 1 Radial (`radius`, `count`), 2 Grid (`countX` × `countZ`; 0 = derived from `count`).
  - `rotateStep` is in **degrees** per copy. `scaleStep` multiplies per copy. `pivot` 0 Start / 1 Center / 2 End.
  - Audio-reactive: `pulse` (+ `pulseStretch`, `pulseRipple`, `pulseJitter`, `pulsePivot`).
  - Instancers nest (an instancer of an instancer), and the cap is 10,000 copies. Every copy is a **draw per part**, so 3 parts × 1,000 copies = 3,000 draws.
- **LOD:** R3NE has no automatic LOD. For distant or background copies, export a decimated version (Blender Decimate modifier, ratio 0.1–0.3, applied on export via `export_apply=True`) as `<name>_lod1.glb` and instance that. Keep the full-res version for the hero.
- Use modifiers (`noiseDisplace3d`, `twist3d`, `wave3d`) on dense meshes only. They displace vertices, so low-poly models just get jagged.

## Route A — Blender headless (template)

`scripts/blender_export_glb.py`, tested with Blender 5.2:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --python "<skill>/scripts/blender_export_glb.py" -- "$HOME/R3NE Assets/meshes/<name>.glb"
```

Copy the script, edit only `build()` (return a list of mesh objects; use the `principled()` / `noise_image()` helpers), and keep `finalize()` + `export_glb()`. The report line `R3NE_EXPORT {...}` gives triangles and size, in Blender axes (z = height).

Exporter call (Blender 4.2+/5.x names; check with `bpy.ops.export_scene.gltf.get_rna_type().properties` if a newer Blender errors):

```python
bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=False,
    export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
    export_tangents=False, export_materials="EXPORT", export_image_format="AUTO",
    export_vertex_color="NONE", export_cameras=False, export_lights=False,
    export_animations=False, export_extras=False)
```

Blender 5.x notes: `material.use_nodes` is always on (don't rely on setting it). Principled inputs are `"Base Color"`, `"Metallic"`, `"Roughness"`, `"Emission Color"`, `"Emission Strength"`, `"Alpha"`. Transparent materials use `material.surface_render_method = "BLENDED"`. `export_format` lists no enum items in background mode, but `"GLB"` works.

## Route B — Blender MCP (live Blender with add-on)

Use it when the user is modeling interactively.
1. Run `get_objects_summary` / `get_blendfile_summary_*` first. Respect their names and structure, and don't delete or modify anything without asking.
2. Build or adjust with `execute_blender_code` (bpy), or use its operators.
3. Check with `render_viewport_to_path` or `get_screenshot_of_window_as_image`.
4. Export the selected objects with the exporter call above plus `use_selection=True`, into `~/R3NE Assets/meshes/`. Then `import_mesh`, or `set_params filePath` to reload an existing loader.

## Route C — procedural glTF without Blender

`scripts/gltf_writer.py` (stdlib only, run with `python3 -I`):

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from gltf_writer import GLB, box, lathe, heightfield, checker_png
glb = GLB()
m = glb.material("Steel", base=(0.6, 0.6, 0.62), metallic=1, roughness=0.35)
glow = glb.material("Glow", base=(1, .2, .6), emissive=(1, .2, .6), emissive_strength=2.5)
for i in range(12):
    glb.add(box(0.2, 0.2 + i * 0.15, 0.2).translated(i * 0.35 - 2, 0, 0), m)
glb.add(lathe([(0, 0), (0.25, 0.1), (0.05, 1.2)], 8, smooth=False).translated(0, 0, -1), glow)
print(glb.save("/Users/<you>/R3NE Assets/meshes/bars.glb"))
```

`Mesh` helpers: `.translated()`, `.scaled()`, `.rotated_y(deg)`, `.flat()` (faceted normals), `.extend()`. Generators: `box(w,h,d)` (bottom at y = 0), `lathe(profile[(r,y)…], segments, smooth)`, `heightfield(size, cells, fn(x,z), flat)`. `glb.add()` merges geometry by material, giving one R3NE part per material. Running the file alone writes a demo island + obelisk.

For a simple OBJ instead: `v x y z` / `vn` / `vt` / `f a/at/an …` lines (1-based) and `usemtl`. Only use OBJ when materials don't matter, since glTF carries PBR.

## Verifying an import

1. Read `import_mesh`'s result: `loadSummary` ("3 parts, 480 verts, 1 texture"), part materials, bounds, warnings.
2. Run `snapshot` on the scene. If the model is black, check lights and normals. If it's invisible, check that it's wired, inside the camera frustum and not tiny. If it's grey, check that `useFileMaterials` is on and no Material node is connected.
3. "File not found" or "No geometry" in `loadSummary` → the path is wrong, the format is unsupported, or the file is empty or broken. Re-export.

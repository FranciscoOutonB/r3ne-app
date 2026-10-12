---
name: r3ne-3d
description: Compose and light 3D scenes in R3NE through its MCP, including importing meshes made outside R3NE (Blender headless, the Blender MCP, or procedural glTF written from Python). Use when the user wants a 3D scene, shot, environment or product render in R3NE; wants to import a model (.glb/.gltf/.fbx/.obj/.usdz) or create one in Blender for R3NE; or asks for camera framing, lighting, materials, fog, depth of field, bloom or ray tracing in a Scene 3D. Triggers on "build a 3D scene", "import this model", "make a low-poly X and put it in R3NE", "light this like golden hour", "escena 3d", "arma una escena 3d", "importa este modelo", "importa este mesh", "haz un modelo en Blender para R3NE", "ilumina la escena", "pon una cámara". For 2D shaders and the general graph basics, see the `r3ne` skill.
disable-model-invocation: false
---

# R3NE 3D scenes (with external meshes)

This skill builds on the `r3ne` skill, which covers the graph basics: Root, typed ports, `create_composition`, and MSL shaders. Load `r3ne` too if you haven't. This skill adds the 3D workflow, mesh import, and the habit of **looking at every step** with `snapshot`.

The MCP tool names below are bare. Their prefix depends on how the server is installed: `mcp__plugin_r3ne_r3ne__*` for the plugin and `mcp__r3ne-dev__*` for the dev checkout.

| Tool | Use it for |
|---|---|
| `health`, `get_graph`, `list_node_types` | Preflight checks. `health` also reports `apiBase` (the port it talks to) |
| `create_node`, `connect_nodes`, `set_params`, `create_composition` | Building the graph |
| `get_node` | Exact port names and current values, a Mesh Loader's parts and bounds, and every Scene 3D setting |
| `import_mesh` | A model file → a Mesh Loader 3D node, wired into a scene, with its load report |
| `look_at` | Aiming a camera or light from an eye point at a target (it does the rotation math) |
| `snapshot` | **Seeing** the render as an image (`offline: true` on a Scene 3D gives an Export-identical frame) |
| `save_project` / `open_project` | Writing or opening a `.r3d` file |

## 1. Preflight (every session)

1. Call `health`. If it fails, the app isn't running: tell the user and stop.
2. Call `get_graph`. If the canvas already has work on it, **ask before `clear_graph` or `open_project`**. You can also build next to the existing graph (place your nodes at x ≥ 1500) and wire your Scene 3D into a free Root `texture_N`.
3. Settle the brief in one or two lines: subject, purpose (a VJ loop, a still, a product shot, a stage previs), mood or time of day, and aspect or resolution. For exploratory asks, choose these yourself and say what you chose.

## 2. Workflow loop

Go through the steps in order, run `snapshot` after each **major** step, and critique the image before moving on (see §4).

1. **Skeleton.** Create a `scene3d` and wire `texture → Root.texture_0` (or a free `texture_N`). Add a `camera3d` wired to `camera`. Set the Scene 3D `resolutionX/Y` (the frame size, independent of the window). Lights go into `light_N`, geometry into `geo_N`. Both are variadic, so use the next free slot from `get_node` (`otherInputs`).
2. **Block-in.** Ground (a `plane3d` with large `width`/`height`, e.g. 200, so its edge disappears into fog), the hero object, and the supporting shapes. Primitives come first; real models come via `import_mesh` (§3). Fix scale now: R3NE works in **meters, +Y up**. Frame with `look_at` (camera eye → hero centre). Take a snapshot.
3. **Lighting.** Use one key light that defines the mood, then fill or rim, then practicals. A `sky3d` gives both an environment (IBL, background) and a sun: wire `sun → light_N` and `environment → environment`. Recipes are in `references/look-recipes.md`. Take a snapshot.
4. **Materials.** File materials from a .glb usually just work. Use `material3d` (presets plus principled sliders) for primitives, or when you want to override a whole model. Take a snapshot of the scene, and of a single Material node to see its preview ball.
5. **Camera and lens.** Choose the focal length (fov ≈ 2·atan(12 / f_mm) in degrees, so 35 mm ≈ 38°, 50 mm ≈ 27°, 85 mm ≈ 16°), height and angle, and composition (keep the hero off-centre and silhouettes clear of each other). For DOF, use `look_at … setFocus: true` with `dofEnabled` and `dofMode 0` on the Scene 3D. Take a snapshot.
6. **Atmosphere and post.** Volumetric fog, bloom, exposure compensation, vignette, and the tonemapper (AgX Punchy is the default). Take a snapshot with `offline: true`.
7. **Iterate** until the critique comes back clean. Change one thing at a time.
8. **Save** to a NEW path, e.g. `save_project` → `~/R3NE Assets/scenes/<slug>.r3d` (written as an absolute path). It refuses to overwrite unless `overwrite: true`, which you pass only when the user asked. Then tell the user the path and what's in the scene.

### Canvas layout and naming

Give every node a descriptive `name` ("Hero Cam 50mm", "Key – Dusk Sun", "Floor Mat") and place nodes in columns so the graph reads left to right:

| x | Column |
|---|---|
| ~0–300 | Textures, Material nodes, sources feeding instancers |
| ~350–650 | Geometry / Mesh Loaders / Instancers (top), lights (middle), camera (bottom) |
| ~1000 | Scene 3D |
| ~1300+ | 2D post chain → Root |

Step y by ~140–160 per node. `import_mesh` places loaders to the left of the scene automatically. You can move nodes later with `set_params {"x":…, "y":…}`.

## 3. Importing meshes made outside R3NE

`import_mesh` takes an absolute path plus `sceneId`, and optionally `materialId`, `scale`, `zUp`, `recenter`, `position`, `rotationDeg`. It creates the Mesh Loader, wires it to the next free `geo_N`, waits for the load, and returns:
- `loadSummary`
- `parts`: one per material, with name, triangles, albedo / metallic / roughness / emission / texture flags
- `boundsMin/Max/Size` in meters, after `scale`
- warnings, such as unit or scale problems and non-glTF formats

**Read the bounds.** A model 180 units tall is in centimeters, so set `scale 0.01`. If `boundsMin.y ≠ 0`, set `positionY = -boundsMin.y` so the model sits on the ground. Use `boundsSize` to frame the camera: distance ≈ (height / 2) / tan(fov / 2) × 1.3.

Choosing a source:
- **Blender headless (default for modeled assets).** Copy `scripts/blender_export_glb.py`, replace `build()`, then run `/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python <script> -- "<abs out.glb>"`. The script handles the scene reset, Principled materials, packed textures, applying transforms, putting the origin at the bottom centre, and the exporter options. It prints a JSON report.
- **Blender MCP (`mcp__Blender__*`).** Use it when the user has Blender open with the add-on. Inspect the scene first (`get_objects_summary`) and don't modify their objects without asking. Export with the same `bpy.ops.export_scene.gltf(...)` options as the template, via `execute_blender_code`.
- **Procedural, no Blender (terrains, lathes, generative forms, data).** Use `scripts/gltf_writer.py`, a stdlib-only GLB writer with `box`, `lathe`, `heightfield`, `flat()`, PBR materials, emissive strength, and embedded PNG. numpy and trimesh are not installed, so don't reach for them.
- **Downloaded or user files.** Prefer .glb. FBX and OBJ work through Assimp but with approximate materials. If something's off, round-trip through Blender (import, fix scale/axes/materials, export .glb).

Store assets in `~/R3NE Assets/meshes/` and textures in `~/R3NE Assets/textures/`, never `/tmp`. Projects reference assets by absolute path, so assets that move or vanish break the `.r3d`.

After re-exporting a file to the **same path**, send `set_params {"filePath": "<same path>"}` to the loader. It doesn't watch the file.

The full checklist, covering units and axes, origin, normals, UVs, PBR mapping, texture limits, polycount budgets, naming, one file per asset vs. one per scene, and LOD/instancing, is in `references/mesh-import.md`.

## 4. Looking at a snapshot critically

Call `snapshot {id: <scene3d>, offline: true}`. Optionally add `savePath` (absolute .png) to keep the full-resolution frame. Then check:
- **Exposure.** Are the blacks crushed (a dark subject against a bright sky usually needs a fill light) or are highlights blown? Use `exposureCompensation` in stops.
- **Readability.** Is the hero's silhouette clear against the background? Separate it with a rim or backlight, a contrasting value, or fog.
- **Scale and grounding.** Does the object sit on the floor? Is there a contact shadow? Are its proportions right?
- **Color.** Emissives with `emissiveStrength` above ~2–3 turn white under AgX Punchy, so lower the strength and let bloom carry the glow. Watch for unintended color casts.
- **Artifacts.** Look for noisy RT reflections on rough floors, a visible plane edge or horizon, z-fighting, black shadow acne, and fog washing everything out.
- **Composition.** Look for overlapping silhouettes (move the background pieces), dead centre framing, and wasted space.

Say in one sentence what you see and what you'll change, then change it.

## 5. Key facts (more in `references/gotchas.md`)

- **Rotation.** The API's `rotationX/Y/Z` are **radians**, and `rotationXDeg/YDeg/ZDeg` are degrees (as the UI shows). Forward is −Z, with pitch = rotationX and yaw = rotationY. Use `look_at` rather than computing angles yourself.
- **Port values** come back as strings in the raw API (`defaultValue`). `get_node` parses them.
- **Menus take indices.** `exposureMode` is 0 Manual, 1 Physical Camera, 2 Auto. `tonemapper` is 0 ACES, 1 AgX, 2 AgX Punchy, 3 PBR Neutral, 4 None. `fogMode` is 0 Simple, 1 Volumetric. `dofMode` is 0 Physical, 1 Manual. `rtMode` is 0 Off, 1 Hybrid, 2 Full RT, 3 Path Tracer. Instancer `mode` is 0 Linear, 1 Radial, 2 Grid.
- **Camera exposure settings** (fStop/ISO/shutter/ND) only change brightness when `exposureMode` is 1. Physical DOF needs `dofEnabled` + `dofMode 0` and a long lens.
- **Emissive surfaces don't light their surroundings.** Put a `pointLight3d` at the emitter with **`castShadows: 0`**. With shadows on, it sits inside the mesh and the mesh shadows everything.
- **A connected Material node overrides every part of a model.** To give one part its own material (glass, say), export that part as a separate file.
- **Vertex colors are ignored.** Use materials or a texture.
- **Build repetition with `instancer3d`**, not duplicated loaders: `meshLoader3d → instancer3d.geometry → scene.geo_N`. Each copy is one draw per part (~10 µs of CPU each), capped at 10,000 — live, think low thousands. Layouts: `mode` 0 Linear / 1 Radial / 2 Grid (`countX` × `countZ`; 0 = from `count`), `pivot` 0 Start / 1 Center / 2 End, or `scatter` 1 Area (`areaX`/`areaZ`) / 2 Surface (wire a mesh into `surface`) with `seed`, `scaleMin`/`scaleMax`, `randomRotation` (°), `alignToNormal`. `pulse` (+ `pulseStretch`, `pulseRipple`, `pulseJitter`, `pulsePivot`) stretches copies from an audio band.
- **Quality first.** New Scene 3D nodes start on `qualityPreset` 1 Auto (0 Custom, 2 Low, 3 Medium, 4 High, 5 Ultra); Auto picks by the Mac's GPU and the resolution and reports `qualityAutoLevel`, `gpu`, `qualityHint`. Set the preset **before** tweaking: sending any preset-controlled key (renderScale, shadows, GTAO, SSR, SSGI, fog quality, RT…) switches it to Custom.
- **Several cameras:** wire Camera 3D nodes into a `cameraSwitch3d` (`camera_1…8` → its `camera` output → `scene.camera`); `index` (1-based) picks the shot, `mode` 0 Cut / 1 Blend (over `blendTime` s) / 2 Mix (fractional index = a move between two cameras). `look_at` the individual cameras, not the switch.
- **Groups:** `group3d` (`geo_N`, `light_N` in, `geometry` out → `scene.geo_N`) moves/rotates/scales its children together; groups nest. One group per object; cameras can't be grouped.

## 6. When to load the references

- `references/mesh-import.md`: before you create or import any external model.
- `references/look-recipes.md`: when lighting or grading a scene, or when the user names a mood (golden hour, neon, night, studio, fog).
- `references/gotchas.md`: when something looks wrong or a parameter "does nothing".
- `references/performance.md`: for live or VJ use, heavy scenes, ray tracing or path tracing, or many instances.

## 7. Style

Ship a working, good-looking first pass fast, then iterate with snapshots. Don't front-load questions. Make creative calls (lens, time of day, palette) and state them in one line. Report back with the scene path, the asset paths, what you changed after looking, and one or two suggested next tweaks.

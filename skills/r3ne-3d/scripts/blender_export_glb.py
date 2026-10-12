"""Build a mesh in headless Blender and export a .glb that R3NE's Mesh Loader reads well.

Run (Blender 4.2+ / 5.x, no UI):
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python blender_export_glb.py -- "/Users/<you>/R3NE Assets/meshes/crystal_rock.glb"

Copy this file next to your asset notes and replace `build()` with your own model.
Everything else (scene reset, PBR materials, packed texture, transform/origin cleanup,
exporter options, report) is the part that makes the file land correctly in R3NE:

  * meters, +Y up after export (Blender is Z-up; the exporter converts with export_yup)
  * transforms applied, origin at the bottom centre → the model sits on y = 0 in R3NE
  * one Principled BSDF per material → glTF metallic-roughness (base color, metallic,
    roughness, emission + strength, alpha, normal map) — R3NE imports each as a part
  * textures packed into the .glb (≤ 2048 px)
  * NO vertex colors (R3NE ignores them), no cameras / lights / animation

Prints a one-line JSON report (objects, triangles, bounds, file size) at the end.
"""

import json
import math
import os
import random
import sys

import bmesh
import bpy

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(os.path.expanduser(ARGV[0])) if ARGV else os.path.expanduser("~/R3NE Assets/meshes/blender_asset.glb")
SEED = 7


# ───────────────────────── helpers ─────────────────────────

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def principled(name, base=(0.8, 0.8, 0.8, 1.0), metallic=0.0, roughness=0.5,
               emission=None, emission_strength=0.0, image=None, alpha=1.0):
    """Material the glTF exporter maps 1:1 to metallic-roughness PBR.

    Keep the node tree simple: Image Texture → Base Color is exported; procedural
    shader nodes (Noise, Voronoi, ColorRamp …) are NOT — bake them to an image first.
    Emission Strength > 1 is written as KHR_materials_emissive_strength (R3NE reads it;
    > 1 makes the surface bloom).
    """
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:  # always on in Blender 5.x
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"   # → glTF alphaMode BLEND
    if image is not None:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def noise_image(name, size, dark, light, grain=0.35):
    """Small packed RGBA image (stdlib noise, no procedural nodes) — gets embedded in the .glb."""
    img = bpy.data.images.new(name, width=size, height=size, alpha=False)
    rnd = random.Random(SEED)
    cells = 8
    lattice = [[rnd.random() for _ in range(cells + 1)] for _ in range(cells + 1)]
    px = []
    for y in range(size):
        for x in range(size):
            fx, fy = x / size * cells, y / size * cells
            ix, iy = int(fx), int(fy)
            tx, ty = fx - ix, fy - iy
            a = lattice[iy][ix] * (1 - tx) + lattice[iy][ix + 1] * tx
            b = lattice[iy + 1][ix] * (1 - tx) + lattice[iy + 1][ix + 1] * tx
            v = (a * (1 - ty) + b * ty) * (1 - grain) + rnd.random() * grain
            px.extend([dark[i] + (light[i] - dark[i]) * v for i in range(3)] + [1.0])
    img.pixels.foreach_set(px)
    img.pack()
    return img


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_object(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    return link(bpy.data.objects.new(name, me))


def finalize(objects, flat=True):
    """Apply rotation/scale, shade, put the combined origin at the bottom centre."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for o in objects:
        for p in o.data.polygons:
            p.use_smooth = not flat
    # Bottom-centre of everything → world origin (Blender Z-up: min z → 0).
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2
    cy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
    mz = min(p.z for p in pts)
    for o in objects:
        o.location.x -= cx
        o.location.y -= cy
        o.location.z -= mz
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)


def export_glb(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",            # one file, textures embedded
        use_selection=False,
        export_apply=True,              # bake modifiers
        export_yup=True,                # Blender Z-up → glTF/R3NE Y-up
        export_texcoords=True,
        export_normals=True,            # keeps flat / custom normals
        export_tangents=False,          # R3NE generates MikkTSpace-style tangents itself
        export_materials="EXPORT",
        export_image_format="AUTO",     # PNG stays PNG, JPEG stays JPEG
        export_vertex_color="NONE",     # R3NE ignores vertex colors — use materials / textures
        export_cameras=False,
        export_lights=False,
        export_animations=False,        # R3NE bakes the static pose (PreTransformVertices)
        export_extras=False,
    )


def report(objects, path):
    bpy.context.view_layer.update()
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objects)
    pts = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    print("R3NE_EXPORT " + json.dumps({
        "path": path,
        "bytes": os.path.getsize(path),
        "objects": [o.name for o in objects],
        "materials": sorted({s.material.name for o in objects for s in o.material_slots if s.material}),
        "triangles": tris,
        # Blender axes (Z-up); in R3NE: x → x, z → y (height), y → -z
        "size_m": {"x": round(hi[0] - lo[0], 3), "depth_y": round(hi[1] - lo[1], 3), "height_z": round(hi[2] - lo[2], 3)},
    }))


# ───────────────────────── the model (replace me) ─────────────────────────

def build():
    """Stylized low-poly 'crystal on a rock': 3 parts / 3 materials (textured stone,
    emissive crystal, gold band). ~1.1 m tall, origin at the bottom centre."""
    rnd = random.Random(SEED)
    stone = principled("Stone", roughness=0.85,
                       image=noise_image("stone_albedo", 256, (0.16, 0.15, 0.17), (0.42, 0.40, 0.38)))
    # Emission strength ~1–2 keeps the hue under AgX Punchy; 4+ reads as white.
    crystal = principled("Crystal", base=(0.1, 0.55, 1.0, 1.0), roughness=0.15,
                         emission=(0.1, 0.6, 1.0, 1.0), emission_strength=1.5)
    gold = principled("Gold", base=(1.0, 0.71, 0.29, 1.0), metallic=1.0, roughness=0.3)

    # Rock: jittered, squashed icosphere (flat shaded later).
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.45)
    for v in bm.verts:
        v.co *= 1.0 + rnd.uniform(-0.12, 0.12)
        v.co.z *= 0.55
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.2))
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:               # simple planar UVs so the stone texture shows
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x + 0.5, loop.vert.co.y + 0.5 + loop.vert.co.z * 0.5)
    rock = mesh_object("Rock", bm, stone)

    # Crystals: hexagonal prisms with a pointed tip, leaning outwards.
    crystals = []
    for i, (h, r, lean, yaw) in enumerate([(0.75, 0.10, 8, 0), (0.5, 0.07, 24, 120), (0.42, 0.06, 28, 240), (0.32, 0.05, 35, 60)]):
        bm = bmesh.new()
        ring_lo, ring_hi = [], []
        for k in range(6):
            a = k / 6 * math.tau
            ring_lo.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0)))
            ring_hi.append(bm.verts.new((r * math.cos(a), r * math.sin(a), h * 0.8)))
        tip = bm.verts.new((0, 0, h))
        for k in range(6):
            n = (k + 1) % 6
            bm.faces.new((ring_lo[k], ring_lo[n], ring_hi[n], ring_hi[k]))
            bm.faces.new((ring_hi[k], ring_hi[n], tip))
        bm.faces.new(list(reversed(ring_lo)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.loops.layers.uv.new("UVMap")
        o = mesh_object(f"Crystal_{i}", bm, crystal)
        o.rotation_euler = (math.radians(lean), 0, math.radians(yaw))
        o.location = (0.06 * math.cos(math.radians(yaw)), 0.06 * math.sin(math.radians(yaw)), 0.38)
        crystals.append(o)

    # Gold band around the rock.
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=0.5, radius2=0.5, depth=0.06)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.2))
    bm.loops.layers.uv.new("UVMap")
    band = mesh_object("GoldBand", bm, gold)
    band.data.materials[0] = gold

    return [rock, band] + crystals


if __name__ == "__main__":
    reset_scene()
    objs = build()
    finalize(objs, flat=True)
    export_glb(OUT)
    report(objs, OUT)

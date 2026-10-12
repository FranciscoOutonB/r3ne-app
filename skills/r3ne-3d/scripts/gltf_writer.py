#!/usr/bin/env python3
"""Write .glb files for R3NE from plain Python (stdlib only — no numpy / trimesh / Blender).

Use it for procedural or data-driven geometry: terrains from a function, lathed objects,
architectural blocks, generative sculptures. Import the result with the `import_mesh` MCP tool.

    python3 gltf_writer.py "/Users/<you>/R3NE Assets/meshes/proc_island.glb"   # demo model

As a library (copy it next to your generator, or add its folder to sys.path):

    from gltf_writer import GLB, Mesh, box, lathe, heightfield, checker_png
    glb = GLB()
    stone = glb.material("Stone", base=(0.5, 0.48, 0.45), roughness=0.9,
                         texture_png=checker_png(256, (90, 86, 80), (130, 124, 116)))
    glow = glb.material("Glow", base=(1, 0.3, 0.6), emissive=(1, 0.3, 0.6), emissive_strength=2)
    glb.add(box(1, 0.2, 1), stone)                     # one mesh per material = one R3NE part
    glb.add(lathe([(0.0, 0.0), (0.3, 0.0), (0.1, 1.5)], 12).translated(0, 0.2, 0), glow)
    glb.save(path)

Conventions R3NE expects (and this writer follows): meters, +Y up, counter-clockwise
front faces, linear base-color factors (texture PNGs are sRGB), UV origin top-left,
one primitive per material (R3NE turns each material into a separate part).
Vertex colors are ignored by R3NE — use materials or a texture instead.
"""

import json
import math
import struct
import sys
import zlib

# ───────────────────────── mesh data ─────────────────────────


class Mesh:
    """Indexed triangle mesh: positions, normals, uvs (per vertex) + triangle indices."""

    def __init__(self, positions=None, normals=None, uvs=None, indices=None):
        self.positions = positions or []
        self.normals = normals or []
        self.uvs = uvs or []
        self.indices = indices or []

    def extend(self, other):
        base = len(self.positions)
        self.positions += other.positions
        self.normals += other.normals
        self.uvs += other.uvs
        self.indices += [i + base for i in other.indices]
        return self

    def translated(self, dx, dy, dz):
        self.positions = [(x + dx, y + dy, z + dz) for x, y, z in self.positions]
        return self

    def scaled(self, sx, sy=None, sz=None):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        self.positions = [(x * sx, y * sy, z * sz) for x, y, z in self.positions]
        self.normals = [_norm((nx / sx, ny / sy, nz / sz)) for nx, ny, nz in self.normals]
        return self

    def rotated_y(self, deg):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        rot = lambda v: (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)
        self.positions = [rot(p) for p in self.positions]
        self.normals = [rot(n) for n in self.normals]
        return self

    def flat(self):
        """Un-share vertices so every triangle gets its face normal (low-poly look)."""
        out = Mesh()
        for t in range(0, len(self.indices), 3):
            a, b, c = (self.positions[i] for i in self.indices[t:t + 3])
            n = _norm(_cross(_sub(b, a), _sub(c, a)))
            for k, i in enumerate(self.indices[t:t + 3]):
                out.positions.append(self.positions[i])
                out.normals.append(n)
                out.uvs.append(self.uvs[i] if self.uvs else (0.0, 0.0))
                out.indices.append(len(out.positions) - 1)
        return out


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


# ───────────────────────── primitives ─────────────────────────


def box(w, h, d):
    """Axis-aligned box, bottom at y = 0, centred on x/z, flat normals, 0..1 UVs per face."""
    x, z = w / 2, d / 2
    faces = [  # (normal, 4 corners counter-clockwise seen from outside)
        ((0, 1, 0), [(-x, h, z), (x, h, z), (x, h, -z), (-x, h, -z)]),
        ((0, -1, 0), [(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)]),
        ((0, 0, 1), [(-x, 0, z), (x, 0, z), (x, h, z), (-x, h, z)]),
        ((0, 0, -1), [(x, 0, -z), (-x, 0, -z), (-x, h, -z), (x, h, -z)]),
        ((1, 0, 0), [(x, 0, z), (x, 0, -z), (x, h, -z), (x, h, z)]),
        ((-1, 0, 0), [(-x, 0, -z), (-x, 0, z), (-x, h, z), (-x, h, -z)]),
    ]
    m = Mesh()
    for n, quad in faces:
        b = len(m.positions)
        m.positions += quad
        m.normals += [n] * 4
        m.uvs += [(0, 1), (1, 1), (1, 0), (0, 0)]
        m.indices += [b, b + 1, b + 2, b, b + 2, b + 3]
    return m


def lathe(profile, segments=24, smooth=True):
    """Revolve a (radius, y) profile (bottom → top) around +Y. smooth=False → faceted."""
    m = Mesh()
    rings = len(profile)
    for j in range(segments + 1):
        a = j / segments * math.tau
        ca, sa = math.cos(a), math.sin(a)
        for i, (r, y) in enumerate(profile):
            # profile tangent → normal (perpendicular in the r/y plane)
            r0, y0 = profile[max(i - 1, 0)]
            r1, y1 = profile[min(i + 1, rings - 1)]
            nr, ny = (y1 - y0), -(r1 - r0)
            l = math.hypot(nr, ny) or 1.0
            m.positions.append((r * ca, y, -r * sa))
            m.normals.append((nr / l * ca, ny / l, -nr / l * sa))
            m.uvs.append((j / segments, 1 - i / max(rings - 1, 1)))
    for j in range(segments):
        for i in range(rings - 1):
            a = j * rings + i
            b = (j + 1) * rings + i
            m.indices += [a, b, a + 1, a + 1, b, b + 1]
    return m if smooth else m.flat()


def heightfield(size, cells, fn, flat=True):
    """Square terrain centred on the origin: y = fn(x, z). UVs span 0..1."""
    m = Mesh()
    n = cells + 1
    for j in range(n):
        for i in range(n):
            x = (i / cells - 0.5) * size
            z = (j / cells - 0.5) * size
            m.positions.append((x, fn(x, z), z))
            m.uvs.append((i / cells, j / cells))
            m.normals.append((0, 1, 0))
    for j in range(cells):
        for i in range(cells):
            a = j * n + i
            m.indices += [a, a + n, a + 1, a + 1, a + n, a + n + 1]
    if flat:
        return m.flat()
    # smooth normals: accumulate face normals
    acc = [[0.0, 0.0, 0.0] for _ in m.positions]
    for t in range(0, len(m.indices), 3):
        ia, ib, ic = m.indices[t:t + 3]
        fnrm = _cross(_sub(m.positions[ib], m.positions[ia]), _sub(m.positions[ic], m.positions[ia]))
        for k in (ia, ib, ic):
            for d in range(3):
                acc[k][d] += fnrm[d]
    m.normals = [_norm(v) for v in acc]
    return m


# ───────────────────────── textures ─────────────────────────


def png_bytes(width, height, rgb_rows):
    """Encode 8-bit RGB rows ([[(r,g,b), …], …]) as PNG (zlib, no filtering)."""
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rgb_rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def checker_png(size=256, a=(60, 60, 60), b=(200, 200, 200), squares=8):
    s = size // squares
    rows = [[a if ((x // s) + (y // s)) % 2 == 0 else b for x in range(size)] for y in range(size)]
    return png_bytes(size, size, rows)


# ───────────────────────── GLB writer ─────────────────────────


class GLB:
    def __init__(self):
        self.materials = []
        self.mat_index = {}
        self.images = []          # (png bytes)
        self.parts = []           # (name, Mesh, material index)
        self.ext_used = set()

    def material(self, name, base=(0.8, 0.8, 0.8), metallic=0.0, roughness=0.5, alpha=1.0,
                 emissive=(0, 0, 0), emissive_strength=1.0, texture_png=None, double_sided=False):
        """glTF metallic-roughness material. Colors are LINEAR 0..1 factors."""
        pbr = {"baseColorFactor": [*base, alpha], "metallicFactor": metallic, "roughnessFactor": roughness}
        if texture_png is not None:
            self.images.append(texture_png)
            pbr["baseColorTexture"] = {"index": len(self.images) - 1}
        mat = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": double_sided}
        if any(emissive):
            mat["emissiveFactor"] = list(emissive)
            if emissive_strength != 1.0:   # > 1 → bloom in R3NE
                mat["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": emissive_strength}}
                self.ext_used.add("KHR_materials_emissive_strength")
        if alpha < 1.0:
            mat["alphaMode"] = "BLEND"
        self.materials.append(mat)
        self.mat_index[name] = len(self.materials) - 1
        return len(self.materials) - 1

    def add(self, mesh, material, name=None):
        """Merge into the part that already uses this material (one primitive per material)."""
        for part in self.parts:
            if part[2] == material:
                part[1].extend(mesh)
                return
        self.parts.append((name or self.materials[material]["name"], Mesh().extend(mesh), material))

    def save(self, path):
        blob = bytearray()
        views, accessors, meshes, nodes = [], [], [], []

        def view(data, target=None):
            while len(blob) % 4:
                blob.append(0)
            v = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
            if target:
                v["target"] = target
            blob.extend(data)
            views.append(v)
            return len(views) - 1

        def acc(values, comps, ctype=5126, target=34962, minmax=False):
            fmt = {5126: "f", 5125: "I"}[ctype]
            flat = [c for v in values for c in (v if comps > 1 else (v,))]
            a = {"bufferView": view(struct.pack(f"<{len(flat)}{fmt}", *flat), target),
                 "componentType": ctype, "count": len(values),
                 "type": {1: "SCALAR", 2: "VEC2", 3: "VEC3"}[comps]}
            if minmax:
                a["min"] = [min(v[i] for v in values) for i in range(comps)]
                a["max"] = [max(v[i] for v in values) for i in range(comps)]
            accessors.append(a)
            return len(accessors) - 1

        for name, m, mi in self.parts:
            if not m.indices:
                continue
            uvs = m.uvs if len(m.uvs) == len(m.positions) else [(0.0, 0.0)] * len(m.positions)
            attrs = {"POSITION": acc(m.positions, 3, minmax=True), "NORMAL": acc(m.normals, 3),
                     "TEXCOORD_0": acc(uvs, 2)}
            prim = {"attributes": attrs, "indices": acc(m.indices, 1, 5125, 34963), "material": mi}
            meshes.append({"name": name, "primitives": [prim]})
            nodes.append({"name": name, "mesh": len(meshes) - 1})

        images = [{"bufferView": view(png), "mimeType": "image/png"} for png in self.images]
        gltf = {
            "asset": {"version": "2.0", "generator": "r3ne-3d gltf_writer.py"},
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": self.materials,
            "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": 0}],
        }
        if images:
            gltf["images"] = images
            gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
            gltf["textures"] = [{"source": i, "sampler": 0} for i in range(len(images))]
        if self.ext_used:
            gltf["extensionsUsed"] = sorted(self.ext_used)
        while len(blob) % 4:
            blob.append(0)
        gltf["buffers"][0]["byteLength"] = len(blob)
        js = json.dumps(gltf, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(blob)
        with open(path, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, total))
            f.write(struct.pack("<I4s", len(js), b"JSON") + js)
            f.write(struct.pack("<I4s", len(blob), b"BIN\x00") + bytes(blob))
        tris = sum(len(m.indices) // 3 for _, m, _ in self.parts)
        return {"path": path, "bytes": total, "parts": [p[0] for p in self.parts], "triangles": tris}


# ───────────────────────── demo ─────────────────────────


def demo(path):
    """Low-poly island (heightfield) + faceted lathe obelisk with an emissive cap."""
    glb = GLB()
    grass = glb.material("Ground", base=(0.30, 0.42, 0.20), roughness=0.95,
                         texture_png=checker_png(128, (70, 96, 52), (88, 118, 64), squares=16))
    stone = glb.material("Obelisk", base=(0.55, 0.52, 0.48), roughness=0.7)
    glow = glb.material("Beacon", base=(1.0, 0.35, 0.1), emissive=(1.0, 0.35, 0.1), emissive_strength=3.0)

    def island(x, z):
        r = math.hypot(x, z)
        bump = 0.08 * math.sin(x * 3.1) * math.cos(z * 2.7)
        return max(0.0, 0.35 * (1 - (r / 2.2) ** 2)) + bump * (r < 2.0)

    glb.add(heightfield(5.0, 24, island), grass)
    glb.add(lathe([(0.0, 0.0), (0.22, 0.0), (0.16, 1.4), (0.0, 1.55)], 6, smooth=False).translated(0, 0.3, 0), stone)
    glb.add(box(0.12, 0.12, 0.12).rotated_y(45).translated(0, 1.88, 0).flat(), glow)
    return glb.save(path)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "proc_island.glb"
    print(json.dumps(demo(out)))

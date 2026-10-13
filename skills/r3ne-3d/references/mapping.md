# Projection mapping and multi-output 3D (Mapping Cameras 3D)

One 3D scene, several cameras rendered at once, each view to its own output.

## Wiring

```
Scene 3D ──scene──▶ Mapping Cameras 3D ◀── camera_1…8 (Camera 3D, or a Camera Switch 3D)
                         │
                         ├─ view_1 ─▶ Server Output (index 1) / Display Output / NDI / Syphon / Mapper slot
                         └─ view_2 ─▶ …
```

- Create it from the Scene 3D inspector (Mapping Cameras ▸ Add Mapping Cameras 3D) or `create_node mappingCameras3d` + `connect_nodes scene → scene`.
- Each connected camera adds a `view_N` texture output. **Unwired views aren't rendered.** The Scene 3D's own camera view is skipped unless its `texture`/`depth` are wired — wire Root or a Display Output too if you want a monitor view.
- Per view: `view_N_width` / `view_N_height` (0 = the camera's `outputWidth/Height`, else the Scene 3D resolution), `view_N_quality` (Same as Scene / Auto / Low…Ultra). `showFrustums` draws each camera's frustum in the viewport (also a toolbar toggle).
- Routing via API: `set_params {sendTo: {view: N, kind: "server", index: 1}}`; kinds: `display` (`displayUUID`/`displayName`), `server` (`index`), `ndi` (`name`), `syphon` (`name`), `mapper` (`mapperId`, `port`), `root`. It creates/reuses and wires the output node (undoable in the UI's "Send to" menu).
- Read a view: `snapshot` on the mapping node with port `view_N` (raw API: `GET /api/nodes/{id}/snapshot?port=view_N`; an unwired view renders on demand). `offline-frame` works on the mapping node. Read-only per view: `rendered`, `connected`, `destinations`, `cpuMs`.

## Rig (move every view as one block)

Input ports `rigPositionX/Y/Z` (scene units) and `rigRotationX/Y/Z` (**degrees**, unlike node `rotationX/Y/Z`) apply one transform over every wired camera, so all views move and turn as a rigid block and keep their calibration to each other — walk a CAVE or dome through the scene. Order is Z·Y·X like 3D nodes, around the rig origin (scene origin + rig position); lens shift, roll and projection are untouched. Keyframable, MIDI-learnable, saved with the project. `set_params {"rigPositionZ": -4, "rigRotationY": 25}` (raw: `PUT /api/nodes/{id}/params {"params": {...}}`). The viewport frustums follow the rig.

## Screen map (projection onto a custom mesh)

Wire the real display surface (an LED tunnel, dome, curved or folded wall — a `meshLoader3d`, primitive or `group3d`) into the `screen` input. The `screenMap` texture output is that surface flattened in its **UV layout**: each texel gets the colour of every view that sees its world point (rig included), averaged where views overlap, or feathered towards each view's edge with `mapEdgeBlend` (0–0.5, 0 = plain average). Texels no view sees are black. Lay the UVs out like the LED processor / media server pixel map and `screenMap` *is* the feed.

- Size: `mapWidth` × `mapHeight` (default 2048 × 1024, clamped 16–16384).
- While `screenMap` is wired, **every** camera's view renders (also unwired `view_N`); at most 8 views are sampled.
- Read it: `snapshot` with port `screenMap` (raw `GET /api/nodes/{id}/snapshot?port=screenMap`, rendered on demand).

**Recipe (immersive surface seen from one spot):** put the cameras at the audience eye point — 5–6 `camera3d` at the eye, `fov 90`, square views (`view_N_width` / `view_N_height` 1024), facing front / back / left / right / up (/ down), i.e. a cube around the viewer. The surface then shows the scene in correct perspective from there. Straight up/down is `rotationXDeg ±90` (now a defined view; it used to need 89.5°). Move the audience with the rig.

**Previs:** load a **copy** of the screen mesh in a second `scene3d` with its own camera, give it a `material3d` (`baseColor` black, `emissiveColor` white, `emissiveIntensity 1`) whose `emissiveMap` is the `screenMap`.

**Worked example:** `~/R3NE Assets/scenes/tunel-led-bosque.r3d` with `~/R3NE Assets/meshes/led-tunnel.obj` — a tunnel 4 m wide, 2.5 m walls + semicircular arch, 10 m long (z 0 → −10); u = cross-section (left wall bottom → arch → right wall bottom), v = length (near → far); mesh `positionZ 5` centres it on an eye at (0, 1.5, 0).

Generating such a mesh: write an OBJ grid whose `vt` is the pixel map (u along the cross-section by arc length, v along the length). The loader flips OBJ v so v runs **down** the image, so write `1 − v` to put the near end on the top row:

```python
import math
W, H, L, nU, nV = 4.0, 2.5, 10.0, 60, 20          # width, wall height, length, segments
r = W / 2
pts = [(-r, H * t, 0) for t in (i / 10 for i in range(10))]               # left wall, up
pts += [(-r * math.cos(a), H + r * math.sin(a), 0)                        # arch, left → right
        for a in (math.pi * i / 20 for i in range(21))]
pts += [(r, H * (1 - i / 10), 0) for i in range(1, 11)]                   # right wall, down
s = [0.0]
for a, b in zip(pts, pts[1:]): s.append(s[-1] + math.dist(a, b))         # arc length → u
out = []
for j in range(nV + 1):
    z = -L * j / nV
    for (x, y, _), d in zip(pts, s):
        out.append(f"v {x:.5f} {y:.5f} {z:.5f}\nvt {d / s[-1]:.6f} {1 - j / nV:.6f}")
n = len(pts)
faces = [f"f {a}/{a} {a+n}/{a+n} {a+n+1}/{a+n+1}\nf {a}/{a} {a+n+1}/{a+n+1} {a+1}/{a+1}"
         for j in range(nV) for i in range(n - 1) for a in [j * n + i + 1]]
open("led-tunnel.obj", "w").write("\n".join(out + faces) + "\n")
```

Pick `mapWidth/Height` to the processor's canvas (or the arc-length : length ratio, here ≈ 11.3 : 10).

## Camera 3D projector options (all off by default)

| Param | Meaning |
|---|---|
| `lensMode` | 0 Field of View, 1 Throw Ratio |
| `throwRatio` | throw distance ÷ image width (0.2–5). hFOV = 2·atan(1/(2T)); focal length = sensor width × T |
| `lensShiftX` / `lensShiftY` | off-axis shift as a fraction of the image (−1…1), + = right / up — like a projector's lens shift; no keystone |
| `roll` | degrees, + = counter-clockwise seen from behind (the node's Z rotation is ignored for cameras) |
| `outputWidth` / `outputHeight` | the projector/screen resolution hint (0 = scene size) |
| `blendLeft/Right/Top/Bottom` | soft-edge widths (0–0.5 of the image) for overlaps |
| `blendGamma` | 1–3 (2.2 typical); the ramp sums to 1 in linear light across an overlap |
| `mask` (texture input) | white = shown, black = hidden (luminance × alpha) |

## Recipes

- **N projectors edge-blended on a wall:** one Camera 3D per projector at the real projector position, `lensMode 1` with the real throw ratio, `lensShiftY` up if the projector sits low, overlapping sides with mirrored blend widths (e.g. projector 1 `blendRight 0.15`, projector 2 `blendLeft 0.15`), each `view_N` → Server Output N (or Display Output on the screen). Import the venue model with `import_mesh` and check the frustums in the viewport.
- **LED strips / odd screens:** set each view's size to the LED processor's input (e.g. 3840×256) and `view_N_quality` Low.
- **Screen previews:** add a Root or Display Output on the Scene 3D's `texture` for a monitor view; the projector views stay independent.

## Gotchas

- Each view has its own renderer (TAA, auto exposure, fog, SSR/SSGI history are per view — no ghosting across projectors); geometry, IBL, local shadow maps, probes, particles and the RT acceleration structure are shared. The sun's cascades follow each camera.
- Cost (M5 Max, 1080p per view, High): ≈ +1.45 ms GPU per extra view; 4 views ≈ 10 ms frame. GPU memory ≈ 150–250 MB per 1080p view. A view's first connection compiles pipelines (~20 ms) — wire views before the show.
- In the editor a Server Output alone doesn't drive rendering; R3NE Server stretches each secondary output to the comp size, so give each view the aspect of its output.
- A Camera Switch shared between the Scene 3D's camera and a mapping view advances once per consumer (cut detection can be missed) — give mapping views their own cameras.
- Screen map: keep the screen mesh **out** of the Scene 3D (the cameras would see it). The same mesh node can't take the `screenMap` as its own material — that's a graph cycle ("Cycle detected"); use a copy for previs. The mesh needs UVs (OBJ `vt`); UV v = 0 is the top row of the map.
- Not available yet: frustums in R3NE Server's Previs.

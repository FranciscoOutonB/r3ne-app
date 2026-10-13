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
- Not available yet: projected footprint on geometry, frustums in R3NE Server's Previs.

# Gotchas: when something looks wrong or "does nothing"

## API and MCP

- **Port values come back as strings.** The raw API (`get_graph`, `create_node`/`set_params` responses) returns input values in `inputs[].defaultValue` as Swift descriptions: `"1.0"`, `"SIMD4<Float>(0.8, 0.8, 0.8, 1.0)"`. `get_node` (compact) parses them into numbers and arrays under `values`. Node-specific settings (Scene 3D render params, Material, Mesh Loader, Sky) are under `params` as real JSON.
- **`set_params` takes a JSON string.** Pass `"{\"intensity\": 6}"` (arrays for colors: `[r,g,b,a]`). Unknown keys are silently ignored, so if nothing changed, check the exact names with `get_node`.
- **Menus are indices.** `exposureMode`, `tonemapper`, `fogMode`, `dofMode`, `rtMode`, Instancer `mode`, `pivot`, etc. take 0, 1, 2… (see SKILL.md §5). Booleans accept `true/false`.
- **A connected port's default value is ADDED as an offset.** When a float port is driven by a connection (e.g. Audio Bands → `emissiveIntensity`), the value set on that port is added to the incoming signal. Set it to 0 if you want only the signal.
- **Variadic inputs.** Scene 3D and Root have `geo_N`, `light_N`, `particles_N`, `splat_N`. Only one empty slot exists at a time and a new one appears after each connection, so read `get_node` → `otherInputs` for the next free one. `import_mesh` does this for you.
- **The Scene 3D must be wired to Root.** Wire `texture → Root.texture_N`, or it isn't part of the live render. `snapshot offline:true` still renders it.
- **Saving and opening.** `save_project` / `open_project` need the render-3d build (older builds 404). `open_project` replaces the graph. Assets are stored as absolute paths.
- **Test instances.** Another app instance can run with `R3NE_API_PORT=<port>`, and the MCP server follows `R3NE_API_PORT` / `R3NE_API_BASE`. Launching extra instances is risky for the user's autosave: they share `~/Library/Application Support/R3Ne/Autosave/` and a single `session.lock`, and an instance's startup cleanup can delete other sessions' folders. Back up that folder before launching, restore anything that vanished, and never touch `session.lock` while the user's R3NE runs. The prefs domain `com.r3ne.nodeengine` is shared too (`defaults export` before, `defaults import` after).
- **Headless.** A hidden or minimized window, or a locked screen, may stop the live render loop. Snapshots then show stale frames and a Mesh Loader never reports its load. `snapshot offline:true` always renders. Dev builds accept `R3NE_HEADLESS_TICK=1`.

## Transforms and aiming

- **Rotation units.** `rotationX/Y/Z` are **radians**. `rotationXDeg/YDeg/ZDeg` are **degrees** (what the inspector shows; if both are sent, `…Deg` wins). `autoRotateX/Y/Z` are rad/s (the inspector shows °/s). `instancer3d.rotateStep` is in **degrees** per copy.
- **Order and forward.** The matrix is T · Rz · Ry · Rx · S. Forward is **−Z**, rotationX = pitch (+ = up), rotationY = yaw. The world forward of a node is (−cos p · sin y, sin p, −cos p · cos y), which only holds with rotationZ 0 (roll rotates the aim). The camera's up vector is always world +Y, so roll is ignored for cameras and straight up/down is degenerate. `look_at` handles all of this and clamps pitch to ±89.5°.
- **Scale.** `scaleX/Y/Z` on any 3D node work through `set_params` / `create_node` on this branch (verified on `cube3d`). Builds before the skill's API fix clamped them to ≤ 10, because the timeline channel range clamped the value. For big objects prefer the geometry's own size ports (`cube3d.size`, `plane3d.width/height`, `sphere3d.radius`, Mesh Loader `scale`), which also keep the normals and shadow bounds sensible.
- **Sky sun.** The `sky3d` sun is aimed with `azimuth`/`elevation` (with `manualSun 1`) or `timeOfDay`/`latitude`/`dayOfYear`, not with rotation. `northOffset` rotates the whole sky.

## Meshes

- **The model doesn't appear.** Is it wired into a scene (`geo_N`, directly or through an instancer or modifier)? An unwired loader never loads. If `loadSummary` is empty, no frame has rendered yet (the window is hidden?). Is it scaled to cm or mm (`boundsSize` in the hundreds)? Is the camera inside it?
- **A Mesh Loader feeding an instancer didn't load** (builds before the skill's fix). Scene 3D cached its geometry list before the instancer had resolved its source, so the mesh was never built. Fixed on render-3d. On older builds, disconnect and reconnect the instancer → scene link.
- **Re-exported the file, nothing changed.** The loader doesn't watch the file. Re-send `set_params {"filePath": "<same path>"}`.
- **Grey model.** A Material node is connected (it overrides all parts), or `useFileMaterials` is false, or the file has no materials (OBJ without MTL, STL, PLY).
- **One part needs a different material.** A connected Material applies to the whole model, so split the part into its own file.
- **Flat-shaded or faceted when it should be smooth (or the other way round).** Normals come from the file. Re-export with the right shading. Smooth normals are only generated when the file has none.
- **Inside-out or missing faces.** Flipped normals or winding: recalculate them outside in Blender, or enable doubleSided on the material (`material3d doubleSided 1`).
- **Vertex colors don't show.** They're not supported. Bake them to a texture, or use materials.
- **Glass from Blender looks opaque.** glTF transmission isn't imported. Override with a `material3d` (transmission 1, ior 1.5) on a separate glass file + `rtMode 1`.
- **Textures missing from a .gltf.** The relative paths broke (moved without the .bin and images). Use .glb.

## Lighting and materials

- **Black scene.** No light in `light_N`, no `environment` (and the procedural IBL is too weak for a dark material), the camera faces away, or `exposureMode 1` with dark camera settings.
- **Emissive object lights nothing.** That's expected (no GI by default). Add a point light at the emitter with `castShadows 0`. With shadows on, the light inside the mesh is fully blocked.
- **Emissive turns white.** Its strength is too high for AgX Punchy. Use 1–2 and let bloom glow.
- **Noisy or grainy reflections on the floor (Hybrid RT).** Lower `rtReflectionMaxRoughness` to ~0.35 so rough surfaces use the cheaper path, or raise the floor's roughness.
- **SSR artifacts** (detached blobs, holes behind objects) are inherent to screen space. Use RT Hybrid for hero reflections.
- **Fog washes everything out.** `volumetricDensity` is too high. 0.02–0.04 is enough. Lower `volumetricAmbient` if the shadows lift.
- **A plane's edge shows as a horizon line.** Make the ground larger (200 m) and let fog swallow it, or frame it out.
- **The 85 mm shot is dark.** Exposure doesn't change with focal length in Manual mode, but framing a darker area does. Raise `exposureCompensation`.

## Camera, exposure and DOF

- **ISO / f-stop / shutter / ND "do nothing".** They only affect brightness with Scene 3D `exposureMode 1` (Physical Camera). Manual (0) uses `exposure`, and Auto (2) meters by itself. `exposureCompensation` works in every mode.
- **No visible DOF.** You need `dofEnabled true` + `dofMode 0` (Physical) and a longer lens with a wide aperture: 50–85 mm at f/1.4–2.8, focused on the subject (`look_at setFocus`). A ~29 mm lens shows almost no blur. Manual DOF (`dofMode 1`) uses `dofFocalDistance`/`dofFocalRange`/`dofBlurStrength` instead.
- **fov is vertical.** fov ≈ 2·atan(12 / f_mm) on a 36 × 24 mm sensor.
- **Physical exposure in daylight is ~5 stops over** by default until camera settings match the scene (the inspector's Match button). Lower ISO or raise the shutter speed, or stay in Manual.

## Snapshots

- **The snapshot looks different from the window.** The snapshot is the node's own render target at the Scene 3D resolution (e.g. 1920×1080), downscaled to ≤1024 px wide. The window letterboxes.
- **Transparent background.** Without a sky or HDRI as background, the Scene 3D background is transparent (`meanAlpha < 1`). JPEG snapshots show it black. Use `format: "png"` to keep the alpha.
- **The live snapshot is mid-adaptation** (auto exposure, TAA history, path tracer samples). Use `offline: true` for a deterministic, Export-identical frame. Re-opening a saved project then gives a byte-identical frame, which makes a good regression check.

## Quality presets, cameras, groups, scatter

- **Presets flip to Custom.** Sending any key a preset controls (renderScale, upscaleMode, shadows, contact shadows, GTAO, SSR, SSGI, `volumetricQuality`, RT options) with a new value switches `qualityPreset` to 0 Custom. Set the preset first, then tweak. Auto re-picks on open (another Mac) and on a resolution change.
- **Camera Switch index** counts the *connected* cameras in slot order (1-based); the MIDI/OSC range is 1–8 whatever the number of cameras. Cut resets temporal history (no TAA smear across the cut); Mix interpolates position, orientation, FOV, focus and exposure (in stops). The viewport and the Camera 3D inspector act on the camera on air.
- **Group 3D:** an Instancer fed a group replaces the group's own transform (same rule as any Instancer source); one group per object; put Twist / Noise / Wave modifiers on the children, not after the group; cameras, particles and splats can't be grouped. Hiding a group also switches its lights off.
- **Scatter Surface** ignores the Instancer's own transform (copies sit on the surface where it is) and takes the surface's position/orientation but not its scale; the surface mesh renders only if it is also wired into the scene. No overlap avoidance — raise `seed`/area or lower `count` if copies collide.
- **Gizmo keys** in the viewport are 1 / 2 / 3 (move / rotate / scale), not W/E/R (W and E fly the camera); Shift snaps 0.1 m / 15° / ×0.1 relative to the drag; ⌥-click selects the object's group.

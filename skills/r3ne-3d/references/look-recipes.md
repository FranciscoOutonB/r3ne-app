# Look recipes: lighting, materials, atmosphere, post

These are starting values that rendered well in R3NE (render-3d branch, AgX Punchy, 1080p). Tune them while looking at `snapshot`s. All keys go through `set_params` / `create_node` params. Scene 3D keys go on the `scene3d` node.

## Scene 3D defaults worth knowing

`tonemapper 2` (AgX Punchy), `exposureMode 0` (Manual, `exposure 1`), physical bloom on (`bloomIntensity 0.8`), TAA on, `fogMode 1` (volumetric, but `fogEnabled` false), `rtMode 0`, `resolutionX/Y 1920×1080`. When no `environment` is connected, the procedural sky lights the scene (IBL) but isn't drawn: the background is transparent (black in JPEG snapshots).

## Light intensity scale

Values marked "tested" were checked in the end-to-end test. The rest are starting points.

| Light | Starting value | Note |
|---|---|---|
| `directionalLight3d` | `intensity` 2–3 | Tested: 3 over-exposes a white floor |
| `sky3d` sun | `sunIntensity` 3 (default) | Tested. Wire `sun → light_N` |
| `areaLight3d` | `intensity` 6–10 for a soft fill ~2–3 m away | Tested at 8. `width`/`height` in meters |
| `pointLight3d` | `intensity` 4–8 with `range` 3–6 | Tested at 6 / range 3 (practical) |
| `spotLight3d` | `intensity` 8–20, `range` 8–15 | `innerAngle`/`outerAngle` in degrees, e.g. 20/35 |

Colors are sRGB picker values `[r,g,b,1]`. Aim spot, directional and area lights with `look_at`.

## Golden hour / dusk backlight (tested end-to-end)

- `sky3d` with `manualSun 1`, `elevation 6–10`, `turbidity 3–5`. Wire `sun → light_N` and `environment → environment` (the sky becomes the background too).
- **Azimuth convention.** Azimuth runs from north (−Z) toward east (+X). The direction toward the sun is (sin az · cos el, sin el, −cos az · cos el). So azimuth 0 puts the sun at −Z, behind the objects for a camera looking −Z. **For a backlight, set `azimuth = −(camera yaw)` mod 360**, where yaw is the `rotationDeg[1]` that `look_at` returns. Example: camera yaw 40° → azimuth 320. For a front or side key, add 180° or ±90°.
- The backlight leaves the camera side dark. Add a warm soft fill: `areaLight3d` 2×1.5 m, `intensity ~8`, color `[1, 0.85, 0.7, 1]`, placed front-left at ~2.5 m and aimed with `look_at`.
- Volumetric haze: `fogEnabled true`, `fogMode 1`, `volumetricDensity 0.02–0.04`, `volumetricAnisotropy 0.75–0.85` (forward scatter glows around the sun). Above ~0.06 everything washes to milk. Light shafts need something that casts shadows between the sun and the camera.
- `exposureCompensation +0.3`, `vignette 0.2–0.3`.

## Emissive "magic" object + practical light (tested)

- Emissive surface: `emissiveStrength` / Material `emissiveIntensity` **1–2** keeps the hue (cyan stays cyan). 4+ blows out to white under AgX Punchy. Bloom (physical, `bloomIntensity 0.6–1`) gives the glow.
- Emissives don't illuminate other surfaces (unless RT/SSGI GI is on). Add a `pointLight3d` at the emitter's centre with the emitter's color, `intensity 4–8`, `range 3`, and **`castShadows 0`**, because a shadowing light inside a closed mesh is blocked by it. This produces the colored pool on the ground and the lit top of the base.

## Neon / club

- Dark scene (no sky background, or a `sky3d` at night: `timeOfDay 21`), `exposureCompensation` 0 to +1.
- Neon tubes: `material3d` with `preset "Neon"`, or `emissiveColor` saturated plus `emissiveIntensity 2–6` (bloom carries it). Use `bloomIntensity 0.8–1.2`.
- Many small lights: a `lightArray3d` (ring/grid/spiral, chase) instead of N point lights.
- Reflective wet floor: `material3d` with `roughness 0.15`, `metallic 0`, plus `ssrEnabled true` (cheap, has screen-space holes) or `rtMode 1` (Hybrid) with `rtReflectionMaxRoughness 0.35`.
- Audio-reactive: `audioInput.sound → audioBands.sound`. Its outputs `subBass, bass, lowMid, mid, highMid, high, brilliance, amplitude` drive any float port: an instancer's `pulse`, a material's `emissiveIntensity`, a light's `intensity`. Insert `rangeRemap` to scale a band (e.g. 0..1 → 0..6). Remember that a connected port's own default value is **added** as an offset.

## Pool of light / theatrical

`spotLight3d` overhead or 45° off-axis, `castShadows 1`, `innerAngle 18`, `outerAngle 30`, `sourceSize 0.05–0.2` (softer edge). Keep the ambient low: `sky3d` `intensity 0.1–0.3`, or no environment and `exposureCompensation` up. A touch of volumetric fog (`volumetricDensity 0.03`, `volumetricLocalLights true`) shows the cone.

## Studio / product

- Three area lights: a big soft key (2×2 m, 45° front-left, intensity ~8), a fill at half that, and a rim behind (strip 2×0.3 m, intensity ~12).
- Seamless background: a large `plane3d` with a `material3d` of `baseColor ~[0.6,0.6,0.62,1]`, `roughness 0.9`, and a curved backdrop if you build one (export from Blender).
- `tonemapper 3` (PBR Neutral) for true-to-color products, 85 mm (fov ≈ 16°) and `dofEnabled` with `fStop 4–8`.

## Materials (`material3d`)

Presets: Default, Gold, Silver, Copper, Brass, Chrome, Mirror, Brushed Aluminum, Titanium, Iron, Glossy Plastic, Matte Plastic, Rubber, Ceramic, Car Paint, Velvet, Glass, Frosted Glass, Tinted Glass, Water, Diamond, Neon, LED Panel, Matte Black, Concrete. Use `{"preset": "Concrete", …}`; explicit params in the same call override the preset (e.g. `baseColor`).

| Look | Params |
|---|---|
| Chrome / mirror | preset `Chrome` or `metallic 1, roughness 0.02–0.08`. Needs something to reflect (sky, HDRI, other objects). For accurate reflections use `rtMode 1` (Hybrid) with `rtReflectionMaxRoughness ~0.35`, so rough floors don't get noisy RT reflections |
| Glass | `transmission 1`, `ior 1.5`, `roughness 0.02` (or preset `Glass`) + `rtMode 1` (Hybrid; `rtRefraction` on by default). Tint with `absorption` + `baseColor`. Water `ior 1.33`, diamond `2.42` |
| Gold (metal) | `metallic 1`, `baseColor [1.0, 0.71, 0.29, 1]`, `roughness 0.25–0.35` |
| Painted / plastic | `metallic 0`, `roughness 0.3–0.6`, `specular 0.5`. Add a clearcoat for car paint (`clearcoat 1`, `clearcoatRoughness 0.03`) |
| Fabric | `sheen 0.5–1`, `sheenColor`, `roughness 0.8` (or preset `Velvet`) |
| Textured | `texture3d` (`filePath` absolute, `colorSpace` auto/sRGB/linear) → `baseColorMap` / `normalMap` / `roughnessMap` (`roughnessChannel` 1 = G for glTF-packed) / `metallicMap` / `emissiveMap` / `aoMap` / `opacityMap`. `uvTilingX/Y` to repeat. `triplanar 1` for models without good UVs |
| Video on a surface | any 2D texture output (video player, shader) → `emissiveMap` (+ `emissiveIntensity`) or `baseColorMap` |

The Material node's own snapshot (`snapshot {id: <material3d>}`) returns its preview sphere. It's a quick check before wiring.

## Camera and lens

- fov (vertical, degrees) ≈ 2·atan(12 / f_mm): 24 mm ≈ 53°, 35 mm ≈ 38°, 50 mm ≈ 27°, 85 mm ≈ 16°, 135 mm ≈ 10°.
- **Physical DOF** needs Scene 3D `dofEnabled true` + `dofMode 0`, and the camera's `fStop` (1.4–2.8 for visible blur) plus `focusDistance` (`look_at … setFocus: true`). 50 mm f/1.8 at 4 m blurs the background visibly. A wide lens (≤ 35 mm) shows almost none. `dofMaxBlur` (% of image height) caps the bokeh.
- A low camera (eye at 0.5–0.8 m) looking slightly up makes props heroic. Eye height of 1.6 m reads as documentary.

## Post

- Bloom: `bloomMode 0` (physical), `bloomIntensity 0.5–1`, `bloomScatter 0.7`. Use `lensDirtIntensity` with a texture on the `lensDirt` input, and `flareIntensity 0.2–0.5` for anamorphic-ish flares.
- Grade: `whiteBalance` (K, e.g. 5000 cools a tungsten scene), `contrast`, `saturation`, lift/gamma/gain per channel, or a `.cube` via `lutPath` (absolute).
- Lens: `vignette 0.2–0.35`, `chromaticAberration 0.2–0.5`, `grain 0.1–0.2`.
- Motion blur: `motionBlurEnabled` follows the camera's `shutterSpeed` (1/x s).
- Exposure: in Manual mode use `exposure` (multiplier) or `exposureCompensation` (stops). Physical Camera mode (`exposureMode 1`) follows the camera's fStop/shutter/ISO/ND (EV 15 = sunny day = ×1), and is often ~5 stops over in daylight scenes until you match it. Auto (`exposureMode 2`) meters like a camera, which is nice for moving lights but makes snapshots time-dependent.

## Scatter: grass, spikes, rocks

- `instancer3d` with `scatter 2` (Surface): wire the ground/sphere mesh into `surface` (and also into the scene so it renders), the blade/spike/rock into `geometry`. `count` 300–2,000 live, `scaleMin 0.6` / `scaleMax 1.4`, `randomRotation 180`, `alignToNormal 1` for spikes on a sphere, 0 for grass that stays upright. Change `seed` for a new layout.
- Flat patch: `scatter 1` (Area) with `areaX`/`areaZ` in metres around the Instancer's position.
- Audio: `audioBands.bass → instancer.pulse` with `pulseRipple 0.03` makes the field breathe outward.

## Camera moves with a fader (Camera Switch Mix)

- Two (or more) Camera 3D nodes aimed with `look_at` (e.g. wide and close), wired into `cameraSwitch3d` → `scene.camera`, `mode 2` (Mix).
- Map a MIDI fader or keyframe `index` from 1 to 2: the shot glides between the cameras (position, aim, lens, focus, exposure). Ease it with a `smoothValue` between the fader and `index`.
- For live cuts use `mode 0` and map `index` to buttons (or the inspector's take buttons); `mode 1` gives a timed dissolve-like move over `blendTime`.

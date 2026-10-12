# R3NE 3D pipeline reference

Load this when building anything 3D or writing a `pbrMaterial`.

## Node types (3D)

| Type | Outputs | Notes |
|---|---|---|
| `scene3d` | `texture` | Composer: collects geometry/light/camera and renders to a texture |
| `cube3d`, `sphere3d`, `plane3d`, `torus3d`, `cylinder3d`, `cone3d` | `geometry` | Primitive meshes; have a `material` input |
| `meshLoader3d` | `geometry` | Loads .glb/.gltf (best: full PBR), .fbx/.obj/.dae/.usdz… — use the `import_mesh` tool (see the `r3ne-3d` skill) |
| `text3d` | `geometry` | CoreText-rasterized text on an alpha-tested quad. Params: `text`, `fontName`, `fontPixelSize` |
| `directionalLight3d`, `pointLight3d`, `spotLight3d` | `light` | One directional → cast shadows |
| `camera3d` | `camera` | Optional; without one, arcball fallback (mouse orbit in viewport) |
| `pbrMaterial` | `material` | Live MSL PBR material; supports `@input` annotations |
| `chromeMirror3d`, `gold3d`, `steel3d`, `glass3d`, `velvet3d`, `neon3d` | `material` | Pre-baked presets |
| `noiseDisplace3d`, `twist3d`, `wave3d` | `geometry` | Vertex modifiers (compute pass). Wrap a geometry. |
| `instancer3d` | `geometry` | Clones a geometry N times in a pattern |
| `hdri` | `texture` | HDR/EXR equirect for IBL/skybox |
| `particleEmitter3d` | `particles` | GPU particle system; outputs `particles` port (connect to `scene3d` or Root `particles_N`) |
| `audioAnalyzer` | float ports | Outputs `bass`, `mids`, `highs`, `volume`, `peak` reactive to mic |

## Transform params (every Node3DBase)

```json
{
  "positionX": 0, "positionY": 0, "positionZ": 0,
  "rotationX": 0, "rotationY": 0, "rotationZ": 0,
  "scaleX": 1, "scaleY": 1, "scaleZ": 1,
  "autoRotateX": 0, "autoRotateY": 0.3, "autoRotateZ": 0
}
```

`rotation*` is radians (what keyframes store); `rotationXDeg/YDeg/ZDeg` take / return the same angles in degrees, as the inspector shows them (when both are sent, `…Deg` wins). `autoRotate*` is rad/sec (the inspector shows °/s) — use small values like 0.2–0.6 for nice spin.

## Material params (geometry primitives)

```json
{"metallic": 1.0, "roughness": 0.1, "emission": [0.0, 0.0, 0.0]}
```

`metallic` 0=dielectric, 1=metal. `roughness` 0=mirror, 1=diffuse.

## Light params

```json
{"intensity": 1.0, "color": [1, 0.9, 0.8], "range": 10.0,
 "innerAngle": 30, "outerAngle": 45}
```

`range` only for point/spot. `inner/outerAngle` only for spot (degrees).

## Camera params

```json
{"fov": 60.0, "nearPlane": 0.1, "farPlane": 100.0}
```

Set position via the standard `positionX/Y/Z`. Aim by setting `rotationX/Y/Z` (radians).

## Scene3DNode params (composer + post-process)

```json
{
  "exposure": 1.0,
  "bloomEnabled": true, "bloomThreshold": 1.0, "bloomIntensity": 0.5,
  "ssaoEnabled": false, "ssaoRadius": 0.5, "ssaoIntensity": 1.0,
  "shadowBias": 0.005,
  "fogEnabled": false, "fogColor": [0.5, 0.55, 0.65], "fogDensity": 0.12, "fogStart": 2.0,
  "dofEnabled": false, "dofFocalDistance": 5.0, "dofFocalRange": 2.0, "dofBlurStrength": 4.0,
  "resolutionX": 1920, "resolutionY": 1080
}
```

Same keys (with `scene3D*` prefix) work as params on the Root node when going direct-to-Root.

## PBRMaterial template (DYNAMIC INPUT MODE)

The body sets fields on `out` (a `MaterialOutput` struct). Don't write the function signature.

```msl
// @input color baseColor 0.8 0.2 0.4 1.0
// @input float metallic 0.9 0.0 1.0
// @input float roughness 0.2 0.0 1.0
// @input float emissive 0.0 0.0 5.0

out.albedo = baseColor.rgb;
out.metallic = metallic;
out.roughness = max(roughness, 0.04);
out.emission = baseColor.rgb * emissive;
```

Available in body:
- `in.uv` (`float2`) — UV coordinates
- `in.worldPos` (`float3`) — world-space position
- `in.worldNormal` (`float3`) — world-space normal (use as `out.albedo`-modulating input)
- `u.time` (`float`)
- `s` — linear-clamp sampler
- All `@input` declared params

Set on `out`:
- `out.albedo` — `float3` linear color
- `out.metallic` — `float` 0..1
- `out.roughness` — `float` 0..1
- `out.emission` — `float3` linear (HDR ok, fed to bloom)

## Minimal "1 cube + 1 sun + 1 camera → Root" composition

```json
{
  "clearFirst": true,
  "nodes": [
    {"type": "cube3d", "params": "{\"positionY\": 0, \"autoRotateY\": 0.4, \"metallic\": 1.0, \"roughness\": 0.2}"},
    {"type": "directionalLight3d", "params": "{\"rotationX\": -0.7, \"rotationY\": 0.5, \"intensity\": 1.5, \"color\": [1, 0.95, 0.85]}"},
    {"type": "camera3d", "params": "{\"positionZ\": 4.0, \"fov\": 50}"}
  ],
  "connections": [
    {"sourceIndex": 0, "sourcePort": "geometry", "targetIndex": -1, "targetPort": "geo_1"},
    {"sourceIndex": 1, "sourcePort": "light",    "targetIndex": -1, "targetPort": "light_1"},
    {"sourceIndex": 2, "sourcePort": "camera",   "targetIndex": -1, "targetPort": "camera"}
  ]
}
```

## Variadic ports on Root

Root grows new `geo_N` / `light_N` / `particles_N` ports automatically as you connect. So you can keep adding geometries and they'll all show up. Numbers are 1-indexed.

## Materials: connecting to a geometry

```json
{
  "nodes": [
    {"type": "torus3d", "params": "{\"autoRotateY\": 0.3}"},
    {"type": "chromeMirror3d"}
  ],
  "connections": [
    {"sourceIndex": 1, "sourcePort": "material", "targetIndex": 0, "targetPort": "material"},
    {"sourceIndex": 0, "sourcePort": "geometry", "targetIndex": -1, "targetPort": "geo_1"}
  ]
}
```

## Modifiers / instancers chain

```
sphere3d → noiseDisplace3d → twist3d → instancer3d → Root.geo_1
```

Each modifier wraps the previous. `instancer3d` clones the final geometry into a pattern. To wire, use the modifier's `geometry` input/output ports — same as connecting a primitive.

---
name: r3ne
description: Build VJ compositions, shaders, and 3D scenes in R3NE (R3NE Node Engine) via its MCP. Use when the user wants to add/edit/connect nodes, write Metal shaders or 3D PBR materials, run a live MSL preview, or build a full visual chain. Triggers on requests like "make a scene with X", "add a blur to Y", "write a shader that does Z", "build a chrome ball lit by neon", "clear the canvas", or any request that mentions R3NE / R3Ne / "the node engine".
disable-model-invocation: false
---

# R3NE — Node Engine MCP Skill

R3NE is a real-time Swift/Metal node-based VJ engine. This skill teaches you to drive it through the `r3ne` MCP server (tool prefix `mcp__r3ne__*`, or `mcp__plugin_r3ne_r3ne__*` when installed as a plugin), which talks to the embedded HTTP API at `localhost:19780` (`R3NE_API_PORT` overrides the port).

> **Building a 3D scene, importing a model, lighting, or a camera shot? Load the `r3ne-3d` skill as well.** It covers the scene workflow (snapshot after every step), `import_mesh` for .glb/.fbx/.obj made in Blender or procedurally, `look_at`, save/open, and the look recipes, gotchas and performance budgets.

## 1. Pre-flight checks (do these first, every session)

1. **Is the app running?** Call `mcp__r3ne__health`. If it errors with "R3NE app is not running", stop and tell the user to launch the R3Ne.app — don't keep retrying.
2. **What's already on the canvas?** Call `mcp__r3ne__get_graph` to see existing nodes. Don't blindly clear — confirm with the user first if there's anything non-trivial.
3. **What can I create?** Call `mcp__r3ne__list_node_types` if you're unsure of a type name. The list is built dynamically from `NodeFactory.swift` and stays in sync with the app.

## 2. Core mental model

- The graph has **exactly one Root node** (the output). Anything not eventually wired to Root won't appear on screen.
- **2D layer** — texture-producing nodes (`shader`, `blur`, `picture`, `videoPlayer`, generators, post-fx). Connect their `texture` output to the Root or to another texture input.
- **3D layer** — geometry nodes (`cube3d`, `sphere3d`, `plane3d`, `torus3d`, `cylinder3d`, `cone3d`, `meshLoader3d`, `text3d`) flow through typed ports (`geometry`, `light`, `camera`, `material`, `particles`) into either a `scene3d` composer node OR directly into Root (which has built-in 3D compositing).
- **Materials**: every geometry has `materialData` (albedo/metallic/roughness/emission). To override with live MSL, create a `pbrMaterial` and connect its `material` output to the geometry's `material` input.
- **Modifiers**: `noiseDisplace3d`, `twist3d`, `wave3d` wrap a geometry's vertex buffer via compute pass. `instancer3d` clones a geometry N times.
- **Post-FX effects work in place (loopback), not in a chain.** Blur, Glow, Kaleidoscope, Tint, Invert, Gradient Recolour and the other Post-FX nodes have **no output port**: they're applied to the node wired into their `texture` input. Wire `source.texture → effect.texture` for each effect, and keep `source.texture → Root.texture_N` (or downstream). Several effects on one source stack **top to bottom by their canvas position** (then left to right), so place them in the order you want. `get_graph` marks them `"postFX": true`. Wiring one as a source fails with an error that explains this. Generators, shaders, Picture/Video and Canvas *do* have a `texture` output.
- **Connections are typed.** `float ↔ float`, `color ↔ float4` are interchangeable. `texture ↔ texture`, `geometry ↔ geometry`, etc. The MCP rejects incompatible pairs and cycles.

## 3. Building a composition — prefer `create_composition`

For anything more than 1–2 nodes, use `mcp__r3ne__create_composition` instead of looping `create_node` + `connect_nodes`. It's atomic, batches shader compilation waits, and reports compilation errors per shader at the end.

**Layout is automatic.** `create_composition` arranges the canvas left to right by data flow, with **Root alone in the right-most column** and Post-FX stacked under the node they apply to (their top-to-bottom order is the effect stack, and it's kept). You can omit `x`/`y`; pass `arrange: false` only to keep hand-picked positions. After editing a graph node by node, call `mcp__r3ne__arrange_graph` to tidy it the same way.

Index convention in the `connections` array: `targetIndex: -1` means "the Root node". You don't list Root in `nodes`.

```json
{
  "clearFirst": true,
  "nodes": [
    {"type": "fractalNoise", "x": 100, "y": 100},
    {"type": "shader", "name": "Tint pink", "x": 400, "y": 100,
     "source": "// @input color tint 1.0 0.4 0.8 1.0\nfloat4 tex = inputTex.sample(texSampler, in.uv);\nreturn float4(tex.rgb * tint.rgb, tex.a);"}
  ],
  "connections": [
    {"sourceIndex": 0, "sourcePort": "texture", "targetIndex": 1, "targetPort": "inputTex"},
    {"sourceIndex": 1, "sourcePort": "texture", "targetIndex": -1, "targetPort": "texture_0"}
  ]
}
```

## 4. MSL shaders — `@input` annotations are your best friend

R3NE auto-wraps the body so you don't write the function signature in DYNAMIC INPUT MODE. Just declare inputs at the top with `// @input` and write the body that returns `float4`.

```msl
// @input float speed 3.0 0.0 20.0
// @input float scale 8.0 1.0 30.0
// @input color tint 0.2 0.6 1.0 1.0
// @input bool invert false
// @input texture inputTex

float2 uv = in.uv;
float wave = sin(uv.x * scale + u.time * speed);
float3 color = tint.rgb * wave;
if (invert) color = 1.0 - color;
return float4(color, 1.0);
```

Available in shader body:
- `in.uv` (`float2`) — normalized 0–1 UV
- `in.position` (`float4`) — clip-space position
- `u.time` (`float`) — seconds elapsed
- `u.resolution` (`float2`) — render-target size in px
- `texSampler` — predeclared linear-clamp sampler

For `pbrMaterial`, the body must set `out.albedo`, `out.metallic`, `out.roughness`, `out.emission`. See `references/3d-pipeline.md` for the PBR template.

After creating or editing a shader, **always check compilation** — `create_shader` and `edit_shader` already do this and return `compilationResult`. If `compilationState != "success"`, read the error and fix.

## 5. 3D pipeline (Scene3D / Root)

Two equivalent ways to render 3D:

**A) Scene3DNode composer**: a dedicated node that emits a texture. Connect geometry/light/camera to it; pipe its `texture` output downstream like any 2D texture. Best for compositing 3D into a 2D layer chain.

**B) Direct to Root**: Root has variadic `geo_N`, `light_N`, `particles_N`, `camera` ports. Connect 3D nodes directly. Root composites them with the 2D `texture_N` layers. No intermediate `scene3d` node needed for the simple case.

A scene needs **at minimum**: 1 geometry + 1 light + (optional) 1 camera. Without a camera, R3NE uses an arcball fallback (mouse-orbitable in viewport). Without a light, everything is black except for emissive surfaces.

For real-world parameter values, see `references/3d-pipeline.md`.

## 6. Common pitfalls

- **See the result.** `snapshot` returns any node's render as an image (Scene 3D, Root, 2D nodes, Material preview). Use it instead of guessing. `get_node` shows one node's ports, with values parsed.
- **Nothing renders**: probably nothing is wired to Root. Call `get_graph` and check the connection list.
- **Black 3D scene**: no light connected, or `intensity` is 0, or camera looking the wrong way.
- **Shader compiled but pink screen**: a runtime issue (NaN, divide by zero). Re-check the MSL.
- **`set_params` did nothing**: parameter name probably doesn't match a port. Call `get_graph` and inspect that node's `inputs` list.
- **Disconnected MCP**: if every tool errors with "fetch failed", the app isn't running. Don't retry — tell the user.
- **Connecting two `texture` nodes to the same input**: the older connection is auto-removed. That's intentional, not an error.
- **Cycle**: rejected with `cycleDetected`. Restructure.
- **"Source port 'texture' not found" / "… is a Post-FX effect and has no output"**: you tried `blur → glow → Root`. Effects don't chain that way: wire the generator into each effect and the generator to Root (see §2).

## 7. When to load the references

- Composing a 3D scene, importing meshes, lighting/camera/post → use the **`r3ne-3d`** skill.
- Writing a `pbrMaterial`, or wiring basics of the 3D node types → load `references/3d-pipeline.md`.
- Writing a non-trivial 2D shader (tracing/feedback/multi-tap) → load `references/shader-patterns.md`.
- Don't load references for one-shot tasks like "set the bloom intensity to 0.7".

## 8. Style

When the task is exploratory ("make something cool with X"), make a creative choice and ship a working scene — don't ask for a 5-bullet design doc first. The user can always tweak after seeing it run. Shorter, working compositions beat long planning loops.

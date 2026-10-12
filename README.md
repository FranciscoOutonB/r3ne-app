# R3NE — Claude Code plugin

Drive [R3NE](https://r3ne.app) (a node-based real-time VFX engine for macOS) from Claude. The plugin bundles:

- **`r3ne` MCP server** — 20 tools for creating shaders, building 3D scenes, importing meshes, wiring nodes, seeing renders (`snapshot`), and saving projects. Talks to the running R3NE.app via `http://127.0.0.1:19780` (`R3NE_API_PORT` / `R3NE_API_BASE` env override).
- **`r3ne` Skill** — teaches Claude the engine's mental model, MSL `@input` annotations, the 3D pipeline (Scene3D / Root composer), and common pitfalls. Auto-loads when you mention R3NE / VJ / shader / 3D scene.
- **`r3ne-3d` Skill** — the 3D scene workflow: plan → skeleton → block-in → lighting → materials → camera → post, verifying each step with `snapshot`; importing meshes made in Blender (headless template script or the Blender MCP) or procedurally (stdlib glTF writer); look recipes, gotchas, and performance budgets for M3/M4/M5.

## Prerequisites

- macOS with R3NE.app installed and running
- Node.js 18+ on `PATH` (the bundled MCP server uses it; install via `brew install node` if needed)

## Install (Claude Code)

```
/plugin marketplace add FranciscoOutonB/r3ne-app
/plugin install r3ne@r3ne-app
```

Or directly from a Git URL:

```
/plugin marketplace add https://github.com/FranciscoOutonB/r3ne-app.git
```

After install, restart Claude Code. Verify with:

```
> are you connected to r3ne?
```

Claude should call `mcp__r3ne__health` and respond with the running app's version.

## What you can ask

- "Clear the canvas and build a chrome torus lit by a neon spot light, slowly rotating"
- "Add a noise displace + twist modifier on the sphere, stack them in that order"
- "Write a 2D shader that does a rainbow stripes warp on the inputTex, with a `speed` slider"
- "Add a fog setting to the scene with density 0.3 and a teal color"
- "What's currently on the graph? Tell me which nodes aren't wired to Root."
- "Haz una escena 3D al atardecer con un cristal low-poly que modeles en Blender, y guárdala"
- "Import ~/R3NE Assets/meshes/chair.glb, light it like a product shot with an 85 mm lens"

## Tools exposed

| Tool | What it does |
|---|---|
| `health` | Ping the embedded API to check the app is up |
| `get_graph` | Dump the full graph — nodes, connections, params, shader source |
| `list_node_types` | All registerable types from `NodeFactory`, grouped by category |
| `list_presets` | Built-in shader templates with their MSL source |
| `clear_graph` | Remove every non-Root node |
| `create_node` | Add a node by type + optional source/params |
| `delete_node` | Remove a node + its connections |
| `connect_nodes` | Wire an output port to a typed input port |
| `disconnect` | Remove a connection by id |
| `set_params` | Update params on an existing node (incl. transforms / scene settings) |
| `create_shader` | Create a shader node, wait for compilation, return errors if any |
| `edit_shader` | Edit MSL source on an existing shader; returns compilation result |
| `get_shader_errors` | Read the compilation state for a shader node |
| `create_composition` | Atomic batch: create N nodes + M connections in one call |
| `get_node` | One node in full: ports with parsed values, transform, Scene 3D / Material / Mesh Loader params |
| `snapshot` | Return a node's render as an image (optionally an Export-identical offline frame; can save the full-res PNG) |
| `import_mesh` | Import a .glb/.gltf/.fbx/.obj/.usdz… as a Mesh Loader, wire it into a scene, report parts and bounds |
| `look_at` | Aim a camera or light from an eye point at a target (optionally set focus distance) |
| `save_project` | Save the graph to a new .r3d (refuses to overwrite unless asked) |
| `open_project` | Open a .r3d (replaces the current graph) |

## Layout

```
r3ne-app/
├── .claude-plugin/
│   ├── marketplace.json     # marketplace manifest (entry point for /plugin marketplace add)
│   └── plugin.json          # plugin manifest
├── .mcp.json                # registers the bundled MCP server
├── skills/r3ne/
│   ├── SKILL.md             # Claude skill — auto-loads when R3NE/shader/3D is mentioned
│   └── references/
│       ├── 3d-pipeline.md
│       └── shader-patterns.md
├── skills/r3ne-3d/
│   ├── SKILL.md             # 3D scene workflow + mesh import
│   ├── references/          # mesh-import, look-recipes, gotchas, performance
│   └── scripts/             # blender_export_glb.py (Blender headless), gltf_writer.py (stdlib GLB)
└── mcp-server/
    ├── package.json
    └── dist/
        └── index.mjs        # esbuild bundle (~1 MB, all deps inlined)
```

## Changelog

- **0.3.1** — `r3ne-3d` skill: Scene 3D quality presets (Auto per GPU) and the live budget table, Camera Switch 3D (Cut / Blend / Mix), Group 3D, Instancer Scatter (Area / Surface) + grid `countX`/`countZ` / `pivot`, gizmo keys, measured Instancer CPU cost (~10 µs per copy). Needs an R3NE build from main 75f5b35 or later.
- **0.3.0** — New `r3ne-3d` skill (3D scene workflow, mesh import from Blender / procedural glTF, look recipes, gotchas, performance budgets). New MCP tools: `get_node`, `snapshot`, `import_mesh`, `look_at`, `save_project`, `open_project`; `R3NE_API_PORT` / `R3NE_API_BASE` env override. `r3ne` skill: sampler name fix (`texSampler`), no `@input int`. Needs an R3NE build from the render-3d branch for save/open, offline snapshots and Mesh Loader load reports.
- **0.2.0** — Initial plugin: `r3ne` skill + bundled MCP server.

## License

MIT — see [LICENSE](LICENSE). The MCP server source is maintained privately; only the bundled output (`mcp-server/dist/index.mjs`) is distributed here.

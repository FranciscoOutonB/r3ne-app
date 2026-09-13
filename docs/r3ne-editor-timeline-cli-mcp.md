# R3NE Editor — Timeline via CLI & MCP (handoff)

> **Heads-up for the R3NE editor chat:** this feature was built in the *R3NE Server*
> chat by mistake — but it's an **R3NE editor** feature. This doc is the handoff so
> you know it exists, where it lives, and how to extend it. Nothing here touches
> R3NeServer; it's all the editor (`R3Ne` target) + repo-root tooling.

Lets you build the editor's **keyframe timeline** programmatically — set per-node
**in/out regions** and **keyframe curves**, drive the **playhead**, and read
**debug/perf stats** — from a Python CLI/library or via MCP tools. Used it to build
a 13-clip video montage on a 10184-wide canvas end to end.

## How it connects
The R3NE editor already runs a loopback HTTP API on **`127.0.0.1:19780`** (see
`R3Ne/API/APIServer.swift`, `APIRouter.swift`) — the same one the bundled `r3ne`
MCP uses for the node graph. This feature adds **timeline endpoints** to that API.
The API is live only while the editor is open.

## Editor changes (`R3Ne/API/APIRouter.swift`)
New routes (all JSON):
- `GET  /api/timeline` — duration, frameRate, and per node: `activeRegions` (in/out)
  + `channels` (animatable params) with `keyframes`.
- `PUT  /api/timeline/settings` — `{duration?, frameRate?}`.
- `PUT  /api/nodes/{id}/regions` — `{regions:[{start,end}]}` — the in/out points
  (`[]` = always active). Backed by `NodeTimelineTrack.activeRegions`.
- `PUT  /api/nodes/{id}/keyframes` — `{parameter, keyframes:[{time,value,interpolation?}], replace?}`.
- `DELETE /api/nodes/{id}/keyframes` — `{parameter?}` (omit = clear all channels).
- `POST /api/timeline/transport` — `{action: play|pause|stop|seek, time?}` (drives `TimelineModel.shared`).
- `GET  /api/stats` — heartbeat + render `fps`/`frameTimeMs` + node/conn counts +
  playhead + connected outputs (Syphon/NDI). `GET /api/health` also returns `fps` now.

`interpolation` ∈ `constant|linear|bezier|easeIn|easeOut|easeInOut|cubicIn|cubicOut|cubicInOut|exponentialIn|exponentialOut|backIn|backOut|elasticOut|bounceOut`.

Model reference: `R3Ne/UI/Timeline/TimelineModel.swift`, `TimelineTrack.swift`
(`NodeTimelineTrack.activeRegions`, `ParameterChannel.keyframes`, `animatableParams(for:)`).
Handlers call `TimelineModel.shared.syncTracks(with: graph.nodes)` first so a
just-created node has a track/channels before the timeline touches it.

## Other editor fixes made alongside (same build)
- **`applyParams` gained a `videoPlayer` handler** (`APIRouter.swift`): `create_node` /
  `set_params` with `{videoPath, isPlaying, isLooping, playbackSpeed, volume, …}` now
  loads + plays a clip. Requesting `isPlaying:true` **arms `autoPlay`** because
  `loadVideo` is async and the load-completion handler only starts playback when
  `autoPlay` is set (setting `isPlaying` alone left clips frozen). Also a small
  `PictureNode` handler (`imagePath` via didSet, `alpha`).
- **Dynamic-port persistence fix** (`NodeBase.swift` + `NodeGraph.swift`): added
  `DynamicPortNode.ensurePort(named:)` (default impl grows a `family_N` input family
  densely up to the requested index). `NodeGraph.connect` calls it before validating
  the target port, so restoring a project whose connections come back **out of order**
  no longer drops high-index `texture_N` layers on Canvas/Root. (Previously
  connections to `texture_5` before slots 2–4 existed were silently lost.)
- **Inspector multi-edit** (`NodeSelection.swift`, `PortEditor.swift`, `ContentView.swift`,
  `NodeGraphViewController.swift`, `NodeGraphView.swift`): selecting several same-type
  nodes and editing Properties applies to all of them. Building blocks:
  `NodeSelection.sameTypePeers(of:)` (uses the node's own `graph` back-ref) +
  `applyToSelected(node){…}` (mutates node + peers, marks each dirty). `PortEditor`
  fans out generic port edits; `Image2DControls`/`Transform2DControls` were converted
  (blend mode, alpha, pos/scale/rotate/anchor, aspect). The inspector now shows a
  representative node on multi-select (`selectedNodeId` = `primarySelectedId`) instead
  of hiding. **To extend to more node types:** wrap that control's `Binding` setter in
  `applyToSelected(node) { $0.prop = v }` — one line per control.

## Client 1 — Python CLI / library (`tools/r3ne_timeline.py`)
Dependency-free (`urllib`). `R3NE()` class + a CLI.
```python
from r3ne_timeline import R3NE, Beats
r = R3NE()
r.set_settings(duration=120, frame_rate=60)
kick = r.node_id("Kick")                 # resolve by display name
r.set_regions(kick, [(0,2),(4,6)])       # in/out
r.tile(kick, clip_len=2, count=8, gap=2)
r.ramp(kick, "intensity", 0, 4, 0, 1, interp="easeOut")
r.lfo("Strobe", "opacity", t0=0, t1=16, freq=4, amp=0.5, offset=0.5)
r.crossfade("SceneA", "SceneB", t=30, dur=2)
r.every_n_beats("Strobe", bpm=128, n=1, count=64)   # beat-synced in/out
r.play(); r.seek(16); r.pause()
print(r.stats())
```
Helpers: `set_regions/keyframes`, `sequence/tile`, `ramp/hold/pulse/lfo/curve`,
`fade_in/fade_out/envelope/crossfade/sequence_crossfade`, `beat_regions/every_n_beats/pulse_beats`,
`Beats(bpm)`, `transport/play/pause/stop/seek`, `health/stats/timeline/graph`.
CLI: `python3 tools/r3ne_timeline.py {get|graph|settings|regions|keyframes|clear|crossfade|beats}`.

## Client 2 — MCP server (`mcp-timeline/index.mjs`)
Dependency-free Node MCP (implements the stdio JSON-RPC by hand). Registered in
`.mcp.json` as **`r3ne-timeline`** (alongside the existing `r3ne` graph server).
Tools: `r3ne_stats`, `r3ne_timeline_get`, `r3ne_timeline_settings`, `r3ne_transport`,
`r3ne_set_regions`, `r3ne_set_keyframes`, `r3ne_clear_keyframes`, `r3ne_crossfade`,
`r3ne_beat_regions`. Accepts a node **id or display name**. `R3NE_API` env overrides
the base URL. (Restart the Claude session to load a newly-added MCP server.)

## Worked example — random-video montage
`videoPlayer → picture (alpha=fade + position/scale) → canvas(WxH) → Root.texture_N`
(Root/canvas `texture_N` inputs are **dynamic** → multi-layer compositor). Per clip:
static transform via a single constant keyframe on `positionX/Y`/`scaleX/Y`, fade via
an `alpha` envelope, appearance window via `set_regions`. To keep a video's real
proportion on a wide canvas: `scaleX = scaleY * videoAspect / canvasAspect`
(full-height, centred = `scaleY=1`, `positionY=0.5`). Read each clip's real aspect
from its node snapshot (`GET /api/nodes/{id}/snapshot` returns w/h).

## Files
- Editor: `swift-app/R3Ne/API/APIRouter.swift` (endpoints + videoPlayer/picture params),
  `swift-app/R3Ne/NodeGraph/Core/NodeBase.swift` + `NodeGraph.swift` (dynamic-port restore),
  `swift-app/R3Ne/View/NodeSelection.swift` + `PortEditor.swift` + `ContentView.swift` +
  `UI/Canvas/NodeGraphViewController.swift` + `NodeGraphView.swift` (multi-edit).
- Tooling (repo root): `tools/r3ne_timeline.py`, `mcp-timeline/index.mjs`, `.mcp.json`.

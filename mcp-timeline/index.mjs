#!/usr/bin/env node
// r3ne-timeline — a tiny, dependency-free MCP server that lets an agent build
// R3NE editor timelines programmatically: set per-node in/out regions and
// keyframe curves via the editor's local API (127.0.0.1:19780).
//
// MCP stdio transport = newline-delimited JSON-RPC. No SDK needed.

import http from "node:http";
import readline from "node:readline";

const BASE = process.env.R3NE_API || "http://127.0.0.1:19780";

// ---- HTTP to the R3NE editor API -------------------------------------------
function api(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body != null ? JSON.stringify(body) : null;
    const u = new URL(BASE + path);
    const req = http.request(
      { hostname: u.hostname, port: u.port, path: u.pathname + u.search, method,
        headers: { "Content-Type": "application/json" } },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          const json = buf ? safeParse(buf) : {};
          if (res.statusCode >= 400) reject(new Error(json?.error || `HTTP ${res.statusCode}: ${buf}`));
          else resolve(json);
        });
      }
    );
    req.on("error", (e) =>
      reject(new Error(`Cannot reach R3NE at ${BASE} (${e.message}). Is the editor open?`)));
    if (data) req.write(data);
    req.end();
  });
}
const safeParse = (s) => { try { return JSON.parse(s); } catch { return s; } };

// Resolve a node id from an id OR a display name.
async function resolveNode(node) {
  if (/^[0-9a-fA-F-]{32,}$/.test(node)) return node;
  const tl = await api("GET", "/api/timeline");
  const byName = (tl.tracks || []).filter((t) => t.name === node);
  if (byName.length === 1) return byName[0].nodeId;
  const contains = (tl.tracks || []).filter((t) => (t.name || "").toLowerCase().includes(node.toLowerCase()));
  if (contains.length === 1) return contains[0].nodeId;
  throw new Error(`No unique node named "${node}". Available: ${(tl.tracks || []).map((t) => t.name).join(", ")}`);
}

// ---- Tools ------------------------------------------------------------------
const TOOLS = [
  {
    name: "r3ne_stats",
    description: "Debug/optimization heartbeat: render fps + frame time, node/connection counts, playhead, and connected outputs (Syphon/NDI clients). Use to check the editor is alive and performing.",
    inputSchema: { type: "object", properties: {} },
    run: () => api("GET", "/api/stats"),
  },
  {
    name: "r3ne_timeline_get",
    description: "Get the R3NE editor timeline: duration, frameRate, and per-node active regions (in/out) + animatable channels with keyframes.",
    inputSchema: { type: "object", properties: {} },
    run: () => api("GET", "/api/timeline"),
  },
  {
    name: "r3ne_timeline_settings",
    description: "Set the timeline duration (seconds) and/or frameRate (fps).",
    inputSchema: {
      type: "object",
      properties: { duration: { type: "number" }, frameRate: { type: "number" } },
    },
    run: (a) => api("PUT", "/api/timeline/settings", a),
  },
  {
    name: "r3ne_transport",
    description: "Drive the timeline playhead: action = play | pause | stop | seek. For seek, also pass `time` (seconds).",
    inputSchema: {
      type: "object",
      required: ["action"],
      properties: { action: { type: "string", enum: ["play", "pause", "stop", "seek"] }, time: { type: "number" } },
    },
    run: (a) => api("POST", "/api/timeline/transport", a.action === "seek" ? { action: "seek", time: a.time } : { action: a.action }),
  },
  {
    name: "r3ne_set_regions",
    description: "Set a node's active IN/OUT regions (when it is visible/active). Pass an empty array to make it always active. `node` is a node id or its display name.",
    inputSchema: {
      type: "object",
      required: ["node", "regions"],
      properties: {
        node: { type: "string" },
        regions: {
          type: "array",
          items: { type: "object", required: ["start", "end"],
                   properties: { start: { type: "number" }, end: { type: "number" } } },
        },
      },
    },
    run: async (a) => api("PUT", `/api/nodes/${await resolveNode(a.node)}/regions`, { regions: a.regions }),
  },
  {
    name: "r3ne_set_keyframes",
    description: "Set keyframes on a node's animatable parameter. Each keyframe: {time, value, interpolation?}. interpolation ∈ constant|linear|bezier|easeIn|easeOut|easeInOut|cubicIn|cubicOut|cubicInOut|exponentialIn|exponentialOut|backIn|backOut|elasticOut|bounceOut. `replace` (default true) clears existing keyframes on that parameter first.",
    inputSchema: {
      type: "object",
      required: ["node", "parameter", "keyframes"],
      properties: {
        node: { type: "string" },
        parameter: { type: "string" },
        replace: { type: "boolean" },
        keyframes: {
          type: "array",
          items: { type: "object", required: ["time", "value"],
                   properties: { time: { type: "number" }, value: { type: "number" },
                                 interpolation: { type: "string" } } },
        },
      },
    },
    run: async (a) => api("PUT", `/api/nodes/${await resolveNode(a.node)}/keyframes`,
      { parameter: a.parameter, keyframes: a.keyframes, replace: a.replace !== false }),
  },
  {
    name: "r3ne_clear_keyframes",
    description: "Clear keyframes for a node's parameter (or all its parameters if `parameter` is omitted).",
    inputSchema: {
      type: "object",
      required: ["node"],
      properties: { node: { type: "string" }, parameter: { type: "string" } },
    },
    run: async (a) => api("DELETE", `/api/nodes/${await resolveNode(a.node)}/keyframes`,
      a.parameter ? { parameter: a.parameter } : {}),
  },
  {
    name: "r3ne_crossfade",
    description: "Crossfade between two nodes: fade `node_out`'s opacity (or `param`) down and `node_in`'s up over [t, t+dur] seconds. Composes with existing keyframes so you can chain crossfades.",
    inputSchema: {
      type: "object",
      required: ["node_out", "node_in", "t", "dur"],
      properties: {
        node_out: { type: "string" }, node_in: { type: "string" },
        t: { type: "number" }, dur: { type: "number" }, param: { type: "string" },
      },
    },
    run: async (a) => {
      const p = a.param || "opacity";
      const out = await resolveNode(a.node_out), inn = await resolveNode(a.node_in);
      await api("PUT", `/api/nodes/${out}/keyframes`, { parameter: p, replace: false, keyframes: [
        { time: a.t, value: 1, interpolation: "easeInOut" }, { time: a.t + a.dur, value: 0, interpolation: "easeInOut" }] });
      await api("PUT", `/api/nodes/${inn}/keyframes`, { parameter: p, replace: false, keyframes: [
        { time: a.t, value: 0, interpolation: "easeInOut" }, { time: a.t + a.dur, value: 1, interpolation: "easeInOut" }] });
      return { crossfade: [a.node_out, a.node_in], t: a.t, dur: a.dur, param: p };
    },
  },
  {
    name: "r3ne_beat_regions",
    description: "Set a node's IN/OUT regions beat-synced: active on every `n`-th beat (for `on` beats), `count` times, at the given `bpm`. `start` is the seconds offset of beat 0.",
    inputSchema: {
      type: "object",
      required: ["node", "bpm", "count"],
      properties: {
        node: { type: "string" }, bpm: { type: "number" }, count: { type: "integer" },
        n: { type: "integer" }, on: { type: "integer" }, start: { type: "number" },
      },
    },
    run: async (a) => {
      const spb = 60 / a.bpm, n = a.n || 1, on = a.on || 1, start = a.start || 0;
      const regions = Array.from({ length: a.count }, (_, i) => ({
        start: start + i * n * spb, end: start + (i * n + on) * spb }));
      return api("PUT", `/api/nodes/${await resolveNode(a.node)}/regions`, { regions });
    },
  },
];

// ---- MCP JSON-RPC over stdio ------------------------------------------------
const send = (msg) => process.stdout.write(JSON.stringify(msg) + "\n");
const result = (id, r) => send({ jsonrpc: "2.0", id, result: r });
const error = (id, code, message) => send({ jsonrpc: "2.0", id, error: { code, message } });

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", async (line) => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  const { id, method, params } = msg;

  if (method === "initialize") {
    return result(id, {
      protocolVersion: params?.protocolVersion || "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "r3ne-timeline", version: "1.0.0" },
    });
  }
  if (method === "notifications/initialized" || method === "notifications/cancelled") return;
  if (method === "tools/list") {
    return result(id, { tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) });
  }
  if (method === "tools/call") {
    const tool = TOOLS.find((t) => t.name === params?.name);
    if (!tool) return error(id, -32602, `Unknown tool: ${params?.name}`);
    try {
      const out = await tool.run(params.arguments || {});
      return result(id, { content: [{ type: "text", text: JSON.stringify(out, null, 2) }] });
    } catch (e) {
      return result(id, { content: [{ type: "text", text: `error: ${e.message}` }], isError: true });
    }
  }
  if (id != null) error(id, -32601, `Method not found: ${method}`);
});

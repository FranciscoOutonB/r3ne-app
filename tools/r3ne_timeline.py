#!/usr/bin/env python3
"""
r3ne_timeline — build R3NE editor timelines programmatically.

Talks to the running R3NE editor's local API (127.0.0.1:19780) to set, per node:
  • active regions  — the in/out points (when a node is visible/active)
  • keyframes        — animation curves per animatable parameter

Use it as a library to script sophisticated montages (compute in/out points and
curves in code) or from the command line for quick edits.

    from r3ne_timeline import R3NE
    r = R3NE()
    r.set_settings(duration=120, frame_rate=60)

    # Find nodes by name (as shown on the canvas / timeline)
    kick   = r.node_id("Kick")
    strobe = r.node_id("Strobe")

    # In/out montage: 8 bars of 2s each, kick active on odd bars, strobe on evens
    r.sequence([kick],   [(i*2, i*2+2) for i in range(0, 16, 2)])
    r.sequence([strobe], [(i*2, i*2+2) for i in range(1, 16, 2)])

    # Animate a parameter: linear ramp, then an LFO
    r.ramp(kick, "intensity", 0, 4, 0.0, 1.0, interp="easeOut")
    r.lfo(strobe, "opacity", t0=0, t1=16, freq=4, amp=0.5, offset=0.5)

CLI examples:
    python3 r3ne_timeline.py get
    python3 r3ne_timeline.py settings --duration 120 --fps 60
    python3 r3ne_timeline.py regions "Kick" 0:2 4:6 8:10
    python3 r3ne_timeline.py keyframes "Kick" intensity 0=0 2=1 4=0 --interp easeInOut
"""

import json
import math
import sys
import urllib.request

BASE = "http://127.0.0.1:19780"

INTERPOLATIONS = [
    "constant", "linear", "bezier", "easeIn", "easeOut", "easeInOut",
    "cubicIn", "cubicOut", "cubicInOut", "exponentialIn", "exponentialOut",
    "backIn", "backOut", "elasticOut", "bounceOut",
]


class R3NEError(RuntimeError):
    pass


class R3NE:
    def __init__(self, base=BASE, timeout=5):
        self.base = base
        self.timeout = timeout

    # -- low level -----------------------------------------------------------
    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode()
        except urllib.error.HTTPError as e:
            raise R3NEError(f"{method} {path} -> {e.code}: {e.read().decode()}") from None
        except urllib.error.URLError as e:
            raise R3NEError(
                f"Cannot reach R3NE at {self.base} ({e.reason}). "
                f"Is the editor open? (API is 127.0.0.1:19780)"
            ) from None
        return json.loads(raw) if raw else {}

    def health(self):
        return self._req("GET", "/api/health")

    def stats(self):
        """Debug/optimization: fps, frame time, node/conn counts, playhead, outputs."""
        return self._req("GET", "/api/stats")

    def graph(self):
        return self._req("GET", "/api/graph")

    def timeline(self):
        return self._req("GET", "/api/timeline")

    def set_settings(self, duration=None, frame_rate=None):
        body = {}
        if duration is not None:
            body["duration"] = duration
        if frame_rate is not None:
            body["frameRate"] = frame_rate
        return self._req("PUT", "/api/timeline/settings", body)

    # -- transport (drive the playhead programmatically) ---------------------
    def transport(self, action, time=None):
        body = {"action": action}
        if time is not None:
            body["time"] = time
        return self._req("POST", "/api/timeline/transport", body)

    def play(self):  return self.transport("play")
    def pause(self): return self.transport("pause")
    def stop(self):  return self.transport("stop")
    def seek(self, time): return self.transport("seek", time)

    # -- node lookup ---------------------------------------------------------
    def node_id(self, name):
        """Resolve a node id from its display name (as shown on the timeline)."""
        for t in self.timeline().get("tracks", []):
            if t.get("name") == name:
                return t["nodeId"]
        # fall back to a case-insensitive / contains match
        cand = [t for t in self.timeline().get("tracks", [])
                if name.lower() in (t.get("name") or "").lower()]
        if len(cand) == 1:
            return cand[0]["nodeId"]
        raise R3NEError(f"No unique node named {name!r}. "
                        f"Available: {[t.get('name') for t in self.timeline().get('tracks', [])]}")

    def params(self, node):
        """Animatable parameter names for a node (id or name)."""
        nid = self._nid(node)
        for t in self.timeline().get("tracks", []):
            if t["nodeId"] == nid:
                return [c["parameter"] for c in t.get("channels", [])]
        return []

    def _nid(self, node):
        # accept a raw id or a name
        return node if "-" in node and len(node) >= 32 else self.node_id(node)

    # -- in/out regions ------------------------------------------------------
    def set_regions(self, node, regions):
        """regions: list of (start, end) seconds. [] = always active."""
        body = {"regions": [{"start": float(s), "end": float(e)} for s, e in regions]}
        return self._req("PUT", f"/api/nodes/{self._nid(node)}/regions", body)

    def sequence(self, nodes, regions):
        """Assign the same in/out regions to one or more nodes."""
        return [self.set_regions(n, regions) for n in nodes]

    def tile(self, node, clip_len, count, start=0.0, gap=0.0):
        """Lay `count` equal in/out regions of `clip_len` back to back."""
        step = clip_len + gap
        return self.set_regions(node, [(start + i * step, start + i * step + clip_len)
                                       for i in range(count)])

    # -- keyframes -----------------------------------------------------------
    def set_keyframes(self, node, parameter, keyframes, interp=None, replace=True):
        """keyframes: list of (time, value) or {time,value,interpolation}."""
        kfs = []
        for k in keyframes:
            if isinstance(k, dict):
                kf = {"time": float(k["time"]), "value": float(k["value"])}
                if k.get("interpolation") or interp:
                    kf["interpolation"] = k.get("interpolation", interp)
            else:
                t, v = k
                kf = {"time": float(t), "value": float(v)}
                if interp:
                    kf["interpolation"] = interp
            kfs.append(kf)
        body = {"parameter": parameter, "keyframes": kfs, "replace": replace}
        return self._req("PUT", f"/api/nodes/{self._nid(node)}/keyframes", body)

    def clear_keyframes(self, node, parameter=None):
        body = {"parameter": parameter} if parameter else {}
        return self._req("DELETE", f"/api/nodes/{self._nid(node)}/keyframes", body)

    # -- curve generators (the "programmatic in/out" sugar) ------------------
    def ramp(self, node, parameter, t0, t1, v0, v1, interp="linear", replace=True):
        """Two keyframes: a straight (or eased) ramp from v0→v1 over [t0,t1]."""
        return self.set_keyframes(node, parameter,
                                  [(t0, v0), (t1, v1)], interp=interp, replace=replace)

    def hold(self, node, parameter, t, v, replace=False):
        """A single constant keyframe at time t."""
        return self.set_keyframes(node, parameter, [{"time": t, "value": v, "interpolation": "constant"}],
                                  replace=replace)

    def pulse(self, node, parameter, times, high=1.0, low=0.0, width=0.05, replace=True):
        """Square pulses to `high` at each time in `times`, back to `low`."""
        kfs = []
        for t in times:
            kfs.append({"time": t, "value": low, "interpolation": "constant"})
            kfs.append({"time": t + 1e-3, "value": high, "interpolation": "constant"})
            kfs.append({"time": t + width, "value": low, "interpolation": "constant"})
        return self.set_keyframes(node, parameter, kfs, replace=replace)

    def lfo(self, node, parameter, t0, t1, freq, amp=0.5, offset=0.5, phase=0.0,
            steps=None, shape="sine", replace=True):
        """Sampled oscillator (sine/tri/saw) baked to keyframes over [t0,t1].
        freq = cycles per second."""
        if steps is None:
            steps = max(8, int((t1 - t0) * freq * 8))  # ~8 samples/cycle
        kfs = []
        for i in range(steps + 1):
            t = t0 + (t1 - t0) * i / steps
            ph = (t - t0) * freq + phase
            frac = ph - math.floor(ph)
            if shape == "sine":
                s = math.sin(2 * math.pi * ph)
            elif shape == "tri":
                s = 4 * abs(frac - 0.5) - 1
            elif shape == "saw":
                s = 2 * frac - 1
            else:
                raise R3NEError(f"unknown shape {shape!r}")
            kfs.append((t, offset + amp * s))
        return self.set_keyframes(node, parameter, kfs, interp="linear", replace=replace)

    def curve(self, node, parameter, points, interp="linear", replace=True):
        """Keyframes from an explicit list of (time, value) points."""
        return self.set_keyframes(node, parameter, points, interp=interp, replace=replace)

    # -- fades & cross-fades (opacity envelopes) -----------------------------
    def fade_in(self, node, t0, dur, param="opacity", to=1.0, interp="easeInOut", replace=False):
        return self.set_keyframes(node, param, [(t0, 0.0), (t0 + dur, to)], interp=interp, replace=replace)

    def fade_out(self, node, t0, dur, param="opacity", frm=1.0, interp="easeInOut", replace=False):
        return self.set_keyframes(node, param, [(t0, frm), (t0 + dur, 0.0)], interp=interp, replace=replace)

    def envelope(self, node, in_t, out_t, in_dur=0.5, out_dur=0.5, param="opacity",
                 interp="easeInOut", replace=True):
        """A full clip envelope: fade in at `in_t`, hold, fade out ending at `out_t`."""
        return self.set_keyframes(node, param, [
            (in_t, 0.0), (in_t + in_dur, 1.0),
            (out_t - out_dur, 1.0), (out_t, 0.0),
        ], interp=interp, replace=replace)

    def crossfade(self, node_out, node_in, t, dur, param="opacity", interp="easeInOut"):
        """Fade `node_out` down and `node_in` up over [t, t+dur]. Composes with
        existing keyframes (replace=False), so you can chain crossfades over time."""
        self.fade_out(node_out, t, dur, param=param, interp=interp)
        self.fade_in(node_in, t, dur, param=param, interp=interp)
        return {"crossfade": [node_out, node_in], "t": t, "dur": dur}

    def sequence_crossfade(self, nodes, clip, dur, start=0.0, param="opacity"):
        """Chain a list of nodes A→B→C… each showing for `clip` seconds with a
        `dur`-second crossfade between them. Builds the opacity envelopes."""
        step = clip
        for i, n in enumerate(nodes):
            t_in = start + i * step
            self.envelope(n, in_t=t_in, out_t=t_in + clip + dur,
                          in_dur=(dur if i > 0 else 0.01), out_dur=dur, param=param)
        return {"chain": nodes, "clip": clip, "dur": dur}

    # -- beat / BPM-synced montages ------------------------------------------
    def beat_regions(self, node, bpm, active_beats, length_beats=1, start=0.0):
        """In/out regions at the given beat indices, each `length_beats` long."""
        return self.set_regions(node, Beats(bpm, start).regions(active_beats, length_beats))

    def every_n_beats(self, node, bpm, n, count, on=1, start=0.0, start_beat=0):
        """In/out on every n-th beat (on for `on` beats), `count` times."""
        return self.set_regions(node, Beats(bpm, start).every(n, count, on, start_beat))

    def pulse_beats(self, node, parameter, bpm, count, every=1, high=1.0, low=0.0,
                    width=0.05, start=0.0):
        """Pulse a parameter to `high` on each beat (every `every` beats)."""
        return self.pulse(node, parameter, Beats(bpm, start).times(count, every),
                          high=high, low=low, width=width)


class Beats:
    """BPM → seconds helper for beat/bar-synced montages."""
    def __init__(self, bpm, start=0.0, beats_per_bar=4):
        self.bpm = float(bpm)
        self.spb = 60.0 / float(bpm)      # seconds per beat
        self.start = float(start)
        self.beats_per_bar = beats_per_bar

    def t(self, beat):
        return self.start + beat * self.spb

    def times(self, count, every=1, start_beat=0):
        return [self.t(start_beat + i * every) for i in range(count)]

    def bar(self, bar_index):
        return self.t(bar_index * self.beats_per_bar)

    def regions(self, active_beats, length_beats=1):
        """In/out regions from a list of beat indices, each `length_beats` long."""
        return [(self.t(b), self.t(b + length_beats)) for b in active_beats]

    def every(self, n, count, on=1, start_beat=0):
        """Regions on every `n`-th beat: on for `on` beats, `count` times."""
        return [(self.t(start_beat + i * n), self.t(start_beat + i * n + on)) for i in range(count)]



# ---- CLI --------------------------------------------------------------------
def _parse_pair(s, sep):
    a, b = s.split(sep, 1)
    return float(a), float(b)


def _main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="r3ne_timeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("get", help="print the full timeline as JSON")
    sub.add_parser("graph", help="print the node graph as JSON")

    s = sub.add_parser("settings", help="set duration / frame rate")
    s.add_argument("--duration", type=float)
    s.add_argument("--fps", type=float)

    r = sub.add_parser("regions", help="set in/out regions: NAME start:end start:end …")
    r.add_argument("node")
    r.add_argument("regions", nargs="*", help="each as start:end (seconds)")

    k = sub.add_parser("keyframes", help="set keyframes: NAME PARAM time=value time=value …")
    k.add_argument("node")
    k.add_argument("parameter")
    k.add_argument("kf", nargs="+", help="each as time=value")
    k.add_argument("--interp", default="linear", choices=INTERPOLATIONS)
    k.add_argument("--add", action="store_true", help="add (don't replace existing)")

    c = sub.add_parser("clear", help="clear keyframes: NAME [PARAM]")
    c.add_argument("node")
    c.add_argument("parameter", nargs="?")

    x = sub.add_parser("crossfade", help="crossfade OUT IN at time for dur seconds")
    x.add_argument("node_out")
    x.add_argument("node_in")
    x.add_argument("t", type=float)
    x.add_argument("dur", type=float)
    x.add_argument("--param", default="opacity")

    b = sub.add_parser("beats", help="beat-synced in/out: NAME --bpm B --n N --count C")
    b.add_argument("node")
    b.add_argument("--bpm", type=float, required=True)
    b.add_argument("--n", type=int, default=1, help="every n-th beat")
    b.add_argument("--count", type=int, required=True)
    b.add_argument("--on", type=int, default=1, help="beats active per hit")
    b.add_argument("--start", type=float, default=0.0)

    args = p.parse_args(argv)
    api = R3NE()

    if args.cmd == "get":
        print(json.dumps(api.timeline(), indent=2))
    elif args.cmd == "graph":
        print(json.dumps(api.graph(), indent=2))
    elif args.cmd == "settings":
        print(json.dumps(api.set_settings(args.duration, args.fps)))
    elif args.cmd == "regions":
        regs = [_parse_pair(x, ":") for x in args.regions]
        print(json.dumps(api.set_regions(args.node, regs)))
    elif args.cmd == "keyframes":
        kfs = [_parse_pair(x, "=") for x in args.kf]
        print(json.dumps(api.set_keyframes(args.node, args.parameter, kfs,
                                           interp=args.interp, replace=not args.add)))
    elif args.cmd == "clear":
        print(json.dumps(api.clear_keyframes(args.node, args.parameter)))
    elif args.cmd == "crossfade":
        print(json.dumps(api.crossfade(args.node_out, args.node_in, args.t, args.dur, param=args.param)))
    elif args.cmd == "beats":
        print(json.dumps(api.every_n_beats(args.node, args.bpm, args.n, args.count,
                                           on=args.on, start=args.start)))


if __name__ == "__main__":
    try:
        _main(sys.argv[1:])
    except R3NEError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

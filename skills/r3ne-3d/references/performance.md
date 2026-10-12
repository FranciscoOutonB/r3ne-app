# Performance budgets (Apple Silicon M3 / M4 / M5)

The measurements come from the development machine, an **M5 Max (40-core GPU)** at 1920×1080. Numbers for other chips are scaled from GPU core counts and memory bandwidth. Treat them as estimates and measure on the target Mac before a show.

## Measure, don't guess

- `R3NE_S3D_PROFILE=1` (env var at launch) adds per-pass GPU timings to the Scene 3D's `params.gpuTimings` (`get_node`). `params.cpuEncodeMs` is the CPU encode time per frame.
- `GET /api/stats` (or `health`) shows live fps and frame time.
- `snapshot offline:true` returns `offlineFrame.gpuMs` for one full frame. The end-to-end test scene (sky + volumetric fog + DOF + area/point lights + 3 meshes + 9 instanced copies, 1080p) took ~4–7.5 ms GPU on the M5 Max.
- Live budget: 16.7 ms per frame at 60 fps, and that covers everything else in the graph too (2D layers, video decode, outputs). Keep the 3D scene under ~8 ms on the show machine.

## Feature costs (1080p, M5 Max)

| Feature | Cost | Notes |
|---|---|---|
| Base deferred + CSM shadows + clustered lights + TAA + GTAO + SSR (all-on raster) | ~1.4–1.7 ms | Default-ish raster path |
| + SSGI | ~+0.9 ms (≈2.5 ms total) | Off by default, noisy, denoised |
| Cinematic post (physical bloom, DOF, motion blur, volumetric fog, grade, lens) | ~0.85 ms | Volumetric fog is the biggest part |
| Hybrid RT (reflections + shadows, 4 lights) | ~2.1 ms RT on top | Needs a hardware-RT chip: M3 or later |
| Path tracer | 1,024 spp at 1080p ≈ 4.3 s offline | Export or stills only, never live |
| `renderScale` 0.75 + MetalFX (`upscaleMode 1`) | Saves ~40% of the per-pixel cost | Good for 4K output |

Rough scaling for the same scene, relative to the M5 Max: M5 Pro ≈ ×1.8, M4 Pro ≈ ×2, M4 Max ≈ ×1.2, M3 Max ≈ ×1.4, base M3/M4/M5 (8–10 GPU cores) ≈ ×4–5. A scene at 5 ms on the M5 Max is roughly 20+ ms on a base M3, so it won't hold 60 fps.

## Geometry budgets (live, 60 fps, with lighting + post)

| Mac | Visible triangles | Draws (parts × copies) | Instancer copies of a ~1k-tri mesh |
|---|---|---|---|
| Base M3 / M4 / M5 | ≤ 1–2 M | ≤ 1,000 | ≤ 1,000 |
| M3/M4/M5 Pro | ≤ 3–5 M | ≤ 2,000 | ≤ 2,000 |
| M3/M4/M5 Max | ≤ 8–10 M | ≤ 3,000 | ≤ 2,000–3,000 |

- **Every instancer copy is a full draw of every part, and costs ~10 µs of CPU** (measured on M5 Max: 2,000 copies ≈ 23 ms CPU, 10,000 ≈ 90–110 ms ≈ 9 fps). The 10,000 cap is a hard limit, not a live budget; Grid and Scatter cost the same. A 3-part model × 1,000 copies = 3,000 draws. Merge materials (atlas textures) on assets meant for heavy instancing.
- Shadows redraw the geometry per cascade or shadow light, so count shadowed lights as multipliers. Turn `castShadows` off on fill lights and practicals.
- Mesh loading happens on the render thread and blocks frames (big FBX/GLB: hundreds of ms). Load before the show, not during it. Keep files ≤ 50 MB and textures ≤ 2K.
- Modifiers (`noiseDisplace3d`, `twist3d`, `wave3d`) run a compute pass over every vertex every frame. They're fine up to a few hundred thousand vertices.

## Quality presets (Scene 3D ▸ Quality)

`qualityPreset`: 0 Custom, 1 Auto (default for new nodes), 2 Low, 3 Medium, 4 High, 5 Ultra. Old projects open as Custom (exactly as saved).

| Level | Upscale / scale | Shadow map × cascades | Contact | GTAO | SSR | SSGI | Fog cell | Ray tracing |
|---|---|---|---|---|---|---|---|---|
| Low | MetalFX 50 % | 1024 × 2 | off | off | off | off | 16 px | off |
| Medium | MetalFX 67 % | 2048 × 3 | on | on | off | off | 12 px | off |
| High | MetalFX 75 % | 2048 × 4 | on | on | on | off | 12 px | off |
| Ultra | native TAA 100 % | 4096 × 4 | on | on | on | on | 8 px | Hybrid reflections + shadows (M3+) |

Auto: score = GPU cores × generation (M1 1.0, M2 1.1, M3 1.3, M4 1.45, M5 1.75); < 12 Low, < 24 Medium, < 45 High, else Ultra; above 1080p the score is divided by (pixel ratio)^0.75 (4K ≈ one level down); < 10 GB GPU working set caps at Medium. Typical 1080p picks: base M3/M4/M5 → Medium, M4/M5 Pro → High, any Max → Ultra (M5 Max at 4K → High). Auto re-picks only on open on another Mac or a resolution change — never during a show.

**Quick check:** read Scene 3D's `frameGpuMs`, `sceneFps` and `qualityHint` (`get_node`). The hint speaks only when frames really drop, and tells GPU-bound (lower the preset) from CPU-bound (too many draws: fewer objects/copies). An idle GPU clocks down and inflates `frameGpuMs`, so judge by `sceneFps` and drops, not the ms alone. Extra knobs: `shadowCascades` 1–4, `volumetricQuality` 0 Low / 1 Medium / 2 High.

## Live / VJ checklist

0. Start from `qualityPreset` Auto (or one level lower for safety on a show machine), then fix only what the look needs.
1. `rtMode 0` (raster) unless the look needs RT reflections or glass. Hybrid only on Pro/Max chips. Full RT and Path Tracer only for renders.
2. `ssgiEnabled false`, `ssrEnabled` only if reflections matter, `taaEnabled true`.
3. For 4K outputs: `renderScale 0.66–0.75` + `upscaleMode 1` (MetalFX).
4. Volumetric fog: `volumetricRange` as small as the scene allows (40–80 m). `volumetricLocalLights false` if spot cones aren't needed.
5. Limit shadowed lights: 1 sun + ≤ 2 spots. Practicals get `castShadows 0`.
6. Use `Auto` exposure only if the lighting changes during the set. Otherwise use Manual, which is stable and predictable.
7. Profile on the actual show Mac with the full graph running (video players, outputs, MIDI).

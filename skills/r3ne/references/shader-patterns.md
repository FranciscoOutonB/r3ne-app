# R3NE shader patterns reference

Load this when writing non-trivial 2D shaders (multi-tap sampling, ray-tracing tricks, signed distance fields, feedback, displacement).

## Available context in `shader` node body

```
in.uv          float2   normalized 0..1 UV
in.position    float4   clip-space position
u.time         float    seconds elapsed
u.resolution   float2   render-target size in pixels
texSampler      sampler  linear-clamp predeclared
```

## `@input` declarations cheat sheet

```msl
// @input float speed 3.0 0.0 20.0           // value, min, max
// @input float amount 0.5                   // value only — UI uses 0..1 default range
// @input color tint 0.2 0.6 1.0 1.0         // r g b a
// @input bool invert false                  // checkbox
// @input texture inputTex                   // texture port
```

Min/max define the inspector slider range. Defaults are saved with the project.

## Common patterns

### Pure generator (no input)

```msl
// @input float scale 8.0 1.0 30.0
// @input color tintA 0.1 0.2 0.4 1.0
// @input color tintB 1.0 0.3 0.7 1.0

float2 uv = in.uv * scale;
float n = sin(uv.x + u.time) * cos(uv.y - u.time * 0.7);
float3 col = mix(tintA.rgb, tintB.rgb, n * 0.5 + 0.5);
return float4(col, 1.0);
```

### Single-tap post-fx (1 input texture)

```msl
// @input texture inputTex
// @input float strength 1.0 0.0 4.0

float4 c = inputTex.sample(texSampler, in.uv);
c.rgb = pow(c.rgb, float3(1.0 / strength));   // gamma curve
return c;
```

### Multi-tap (blur, edge detect, etc.)

```msl
// @input texture inputTex
// @input float radius 4.0 0.0 32.0

float2 px = 1.0 / u.resolution;
float3 acc = float3(0.0);
const int N = 9;
const float2 taps[9] = {
    float2( 0,  0), float2( 1,  0), float2(-1,  0),
    float2( 0,  1), float2( 0, -1), float2( 1,  1),
    float2(-1, -1), float2( 1, -1), float2(-1,  1)
};
for (int i = 0; i < N; ++i) {
    acc += inputTex.sample(texSampler, in.uv + taps[i] * px * radius).rgb;
}
return float4(acc / float(N), 1.0);
```

### UV displacement

```msl
// @input texture inputTex
// @input float amount 0.05 0.0 0.5
// @input float speed 0.5 0.0 4.0

float2 uv = in.uv;
uv.x += sin(uv.y * 20.0 + u.time * speed) * amount;
return inputTex.sample(texSampler, uv);
```

### Two-input mix

```msl
// @input texture texA
// @input texture texB
// @input float blend 0.5 0.0 1.0

float4 a = texA.sample(texSampler, in.uv);
float4 b = texB.sample(texSampler, in.uv);
return mix(a, b, blend);
```

## Gotchas

- **`fragment` keyword in DYNAMIC INPUT MODE**: don't write it. Just write the body that returns `float4`. R3NE wraps it.
- **FULL MODE**: if you write the full function signature (`fragment float4 ...`), `@input` annotations are ignored — you must declare uniforms yourself in `ShaderUniforms`. Avoid unless you have a specific reason.
- **`texSampler` sampler**: predeclared (linear, clamp-to-edge).
- **Texture out of bounds**: linear sampling clamps to edge. No wrap unless you change the sampler.
- **Performance**: keep loops bounded by a `const int` (or a literal) so the compiler can unroll. There is no `int` `@input` type — use a `float` input and `int(x)` it in the body if you need a runtime count (slower, no unroll).
- **Pink screen**: usually NaN somewhere. Common causes: divide-by-zero, sqrt of negative, log of zero. Use `max(x, 1e-5)` defensively.

## Iterating on a live shader

```
1. create_shader / edit_shader with new source
2. The MCP automatically waits ~500ms then calls get_shader_errors
3. If compilationState != "success", read the error message — line numbers are 1-indexed against your source
4. Fix and edit_shader again
```

Don't keep blindly retrying. Read the error.

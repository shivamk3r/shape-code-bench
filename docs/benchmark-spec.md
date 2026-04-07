# Benchmark Spec

## 1. Vision

`ui-bench` measures how well a model can reverse-engineer a simple rendered scene into executable drawing code.

The benchmark question is:

> Given a rendered synthetic image, can a model infer the program that generated it well enough to recreate the same image?

This is a controlled perception-to-program benchmark, not a general image-generation benchmark.

## 2. Implemented V1 Stack

The current V1 implementation uses:

- Python `3.12`
- `uv` for dependency management and `.venv` creation
- A benchmark-owned Python-like DSL
- `Pillow` for deterministic raster rendering
- `numpy` for evaluation metrics

The current package lives under `src/ui_bench/` and is covered by `pytest` tests in `tests/`.

## 3. V1 Representation

V1 uses a tiny project-owned DSL rather than a full external graphics API.

Why this is the right starting point:

- It keeps the task focused on visual reasoning instead of library trivia.
- It makes execution deterministic.
- It reduces syntax noise for models.
- It lets the benchmark enforce a safe restricted parser.

The evaluator does not execute arbitrary Python. It parses a narrow whitelist of top-level function calls and dispatches only approved drawing operations.

### Primitive API

```python
filled_circle(cx=128, cy=128, radius=40)
circle(cx=300, cy=220, radius=60, stroke=4)
filled_square(cx=220, cy=360, size=81)
square(cx=380, cy=120, size=80, stroke=3)
```

### Canonical Serialization Rules

- One function call per line.
- Fixed keyword order per primitive.
- Integer parameters only.
- Normalized whitespace.
- No imports or boilerplate.

### Parser Restrictions

- Only top-level expression statements are allowed.
- Each expression must be a function call to one of the four approved primitives.
- Keyword arguments only; positional arguments are rejected.
- Argument values must be integer literals.
- Imports, variables, loops, comprehensions, attribute access, and arbitrary Python are rejected.

### Parameter Validation Rules

- `cx` and `cy` must be integers in `[0, 511]`.
- `radius` and `size` must be integers in `[1, 512]`.
- `circle.stroke` must be in `[1, radius]`.
- `square.stroke` must be in `[1, ceil(size / 2)]`.
- Shapes may extend beyond the canvas and are clipped deterministically by the renderer.

## 4. Renderer Semantics

The renderer produces `512x512` grayscale images with:

- white background `255`
- black foreground `0`
- deterministic Pillow drawing semantics

Exact bounds are:

- Circle bounds: `left = cx - radius`, `top = cy - radius`, `right = cx + radius`, `bottom = cy + radius`
- Square bounds: `left = cx - size // 2`, `top = cy - size // 2`, `right = left + size - 1`, `bottom = top + size - 1`

The renderer implementation plus the renderer snapshot tests are the normative V1 raster semantics.

### Draw Order Nuance

Program order is preserved in the AST, serializer, and renderer loop.

However, because V1 uses only black shapes on a white background, the final raster is effectively the union of black pixels touched by any shape. In practice, that makes overlapping scenes order-invariant in V1 even though the system preserves draw order structurally.

True draw-order-sensitive evaluation is deferred until a future version adds richer layering semantics.

## 5. Dataset Generation

Each sample is generated from a latent scene, then serialized into canonical DSL, then rendered into a PNG.

Generation rules:

1. Choose a difficulty tier.
2. Sample the number of shapes and parameter ranges for that tier.
3. Sample primitive types, positions, sizes, and stroke widths from a seeded RNG.
4. Apply tier-specific placement constraints such as low overlap or optional clipping.
5. Serialize the latent scene into canonical DSL.
6. Render and save the PNG plus JSON metadata.

Implementation rule:

- Use only `random.Random(seed)` for determinism.

### Sample Metadata

Each JSON metadata file includes:

- `sample_id`
- `split`
- `difficulty`
- `seed`
- `image_size`
- `num_shapes`
- `shape_inventory`
- `ground_truth_program`
- `render_config`

Generated samples are stored under `data/generated/<split>/<difficulty>/`.

## 6. Difficulty Tiers

Difficulty comes from visual complexity, not from changing the DSL itself.

### Easy

- `1-3` shapes
- size or radius in `[64, 160]`
- stroke in `[2, 6]`
- no clipping
- minimal bounding-box overlap via rejection sampling

### Medium

- `3-6` shapes
- size or radius in `[32, 128]`
- stroke in `[2, 8]`
- moderate overlap allowed
- limited clipping via mixed interior and full-range placement

### Hard

- `6-10` shapes
- size or radius in `[16, 128]`
- stroke in `[1, 10]`
- overlap encouraged
- partial clipping allowed

Hard scenes preserve program order, but they are still raster order-invariant under the current black-only palette.

## 7. Evaluation

The primary score is render-based.

### Primary Metrics

- exact pixel match
- pixel accuracy
- foreground IoU
- aggregate reporting by difficulty tier

### Secondary Signals

- parse success rate
- execution success rate
- canonical format compliance

### Failure Handling

Predictions fail closed on:

- invalid syntax
- unsupported function names
- missing or duplicate arguments
- unexpected arguments
- out-of-range values
- invalid stroke settings

If parsing or execution fails, the prediction receives a scored failure with zero similarity metrics and a populated `error_type`.

## 8. CLI

The package exposes these commands:

- `ui-bench generate`
- `ui-bench render`
- `ui-bench eval`

Typical usage:

```bash
uv run ui-bench generate --split train --difficulty easy --count 4 --seed 0
uv run ui-bench render --program-file sample.dsl --output-file sample.png
uv run ui-bench eval --target-image target.png --prediction-file prediction.dsl
```

## 9. Repository Shape

The implemented repository shape is:

```text
ui-bench/
  README.md
  AGENTS.md
  pyproject.toml
  uv.lock
  src/
    ui_bench/
      cli.py
      dsl.py
      evaluator.py
      generator.py
      renderer.py
      types.py
  tests/
    test_cli.py
    test_dsl.py
    test_evaluator.py
    test_generator.py
    test_renderer.py
  docs/
    benchmark-spec.md
    research-landscape.md
  data/
    generated/
```

## 10. Prompting Protocol

Each evaluated model should receive:

- the target image
- a concise DSL description
- an instruction to return code only
- a standardized formatting template

Recommended prompt constraints:

- no chain-of-thought request
- no explanation in output
- fixed or standardized temperature
- output length capped high enough for the DSL

## 11. Next Steps

The benchmark core now exists. The next recommended steps are:

1. Add model adapters on top of the current evaluator.
2. Add reporting utilities for aggregate tables and per-slice diagnostics.
3. Expand the DSL only after the current V1 baseline is stable.

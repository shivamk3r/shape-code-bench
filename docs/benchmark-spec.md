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
- a benchmark-owned Python-like DSL
- `Pillow` for deterministic raster rendering
- `numpy` for evaluation metrics
- the OpenAI Python SDK for the first live multimodal adapter
- `python-dotenv` for local `.env` loading

The package lives under `src/ui_bench/` and is covered by `pytest` tests in `tests/`.

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

### Smoke-Test Dataset Rule

The reusable live smoke-test dataset contains exactly:

- 1 `easy` sample with a fixed seed
- 1 `medium` sample with a fixed seed

This rule exists specifically to keep first-run OpenAI validation cheap.

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

## 8. Adapter Layer

The end-to-end runner uses a provider-agnostic adapter interface with three live LLM-relevant implementations plus two non-LLM baselines.

### Adapter Interface

- `PredictionRequest`: sample id, image path, system instruction, user prompt text
- `PredictionResult`: raw text, normalized text, model id, request id, usage, latency, adapter error fields
- `ModelAdapter.predict(...) -> PredictionResult`

### OpenAI Responses API Adapter

- provider: `openai`
- API: Responses API
- image input: Base64 `data:image/png;base64,...`
- default model: `gpt-5.5`
- default `reasoning_effort`: `low`
- default image `detail`: `low`
- default `max_output_tokens`: `256`
- retry policy: none

Local development loads `OPENAI_API_KEY` from process env, with `.env` auto-load as a convenience fallback.

### OpenAI Codex CLI Adapter

- provider: `codex`
- transport: `subprocess.run` against `codex exec`
- image input: `-i <image_path>` flag on `codex exec`
- default model: `gpt-5.5`
- default sandbox: `read-only`
- default timeout: `180s` per sample
- default retries: `2` with exponential backoff
- `reasoning_effort`: unset by default; when set, threaded as `-c reasoning_effort=<value>`
- output captured via `--output-last-message`
- authenticates against the user's ChatGPT login; no API tokens consumed

### Claude Code CLI Adapter

- provider: `claude`
- transport: `subprocess.run` against `claude --print`
- image input: attached via Claude Code's `@<path>` file-reference syntax in the prompt body, with `--add-dir <image-parent>` granting read access
- default model: `claude-opus-4-7[1m]`
- default effort: `medium` (one of `low|medium|high|xhigh|max`, threaded as `--effort`)
- default timeout: `240s` per sample
- default retries: `2` with exponential backoff
- session persistence is disabled via `--no-session-persistence`; output captured from stdout with `--output-format text`
- authenticates against the user's Claude subscription; no API tokens consumed

## 9. Prompting Protocol

The first runner uses a fixed zero-shot prompt only.

Each evaluated model receives:

- a system instruction to return DSL code only
- a short textual DSL description
- the target image

Prompt constraints:

- no chain-of-thought request
- no explanation in output
- no markdown fences requested
- no few-shot examples yet

## 10. Runner And Artifacts

The package exposes:

- `ui-bench generate`
- `ui-bench render`
- `ui-bench eval`
- `ui-bench run`

Typical model run:

```bash
uv run ui-bench run \
  --dataset-dir data/generated/train \
  --provider openai \
  --model gpt-5.5 \
  --reasoning-effort low \
  --image-detail low \
  --max-output-tokens 256 \
  --limit 2
```

Run artifacts are written under `data/runs/<run_id>/`:

- `run_config.json`
- `summary.json`
- `samples/<sample_id>.json`

Each per-sample file includes image path, metadata path, raw prediction, normalized prediction, metrics, and adapter metadata.

## 11. Testing Strategy

Default `pytest` runs stay fully offline.

Coverage includes:

- parser and serializer tests
- renderer snapshot tests
- generator reproducibility and difficulty-bound tests
- evaluator tests
- adapter tests with mocked OpenAI / Codex / Claude Code CLI subprocess behavior
- runner tests with a fake adapter
- CLI tests for `generate`, `render`, `eval`, and `run`

The live smoke tests are:

- opt-in only (`UI_BENCH_RUN_LIVE_OPENAI=1` and `UI_BENCH_RUN_LIVE_CODEX=1`)
- skipped by default
- capped at 2 local examples each

## 12. Repository Shape

The implemented repository shape is:

```text
ui-bench/
  README.md
  AGENTS.md
  pyproject.toml
  uv.lock
  src/
    ui_bench/
      adapters/
      cli.py
      dsl.py
      evaluator.py
      generator.py
      normalization.py
      prompts.py
      renderer.py
      runner.py
      types.py
  tests/
    test_adapters.py
    test_baselines.py
    test_claude_code_adapter.py
    test_cli.py
    test_codex_adapter.py
    test_dsl.py
    test_evaluator.py
    test_generator.py
    test_live_codex_smoke.py
    test_live_openai_smoke.py
    test_normalization.py
    test_renderer.py
    test_runner.py
  docs/
    benchmark-spec.md
    research-landscape.md
  data/
    generated/
    runs/
```

## 13. Next Steps

The benchmark core and first live runner now exist. The next recommended steps are:

1. Add richer aggregate reporting and per-slice diagnostics.
2. Characterize the current baseline on small pilot runs before expanding scope.
3. Add additional providers or prompt regimes only after the current zero-shot OpenAI baseline is stable.

# ui-bench

`ui-bench` is a synthetic benchmark for testing whether a multimodal model can look at an image and reconstruct the executable drawing program that generated it.

The core loop is:

1. Sample a scene made of simple geometric primitives.
2. Convert that scene into canonical code in the benchmark DSL.
3. Render the image at `512x512`.
4. Ask a model to observe the image and return code in the same DSL.
5. Parse and execute the predicted code safely.
6. Render the prediction and compare it with the original image.

This gives us a controlled way to measure visual understanding plus structured code generation.

## V1 Stack

The implemented V1 core uses:

- Python `3.12`
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A local `.venv` for the project environment
- A benchmark-owned Python-like DSL
- [`Pillow`](https://pillow.readthedocs.io/) for deterministic raster rendering
- `numpy` for metric computation
- the OpenAI Python SDK for the first live multimodal adapter
- `python-dotenv` for local `.env` loading

The benchmark target stays intentionally small in V1:

- Canvas size: `512x512`
- Primitive shapes: `circle`, `filled_circle`, `square`, `filled_square`
- Palette: white background with black shapes
- Primary score: render-based, not exact code-string match
- Difficulty tiers: `easy`, `medium`, `hard`

## Important V1 Nuance

The renderer preserves program order, but with a binary black-on-white palette the final raster is effectively order-invariant: later shapes can add black pixels, but they never erase earlier ones.

That means overlap still matters in V1, but true draw-order-sensitive scenes are deferred until a future version adds richer layering semantics such as multiple colors or explicit erasing.

## Quickstart

```bash
python3 -m pip install --user uv
uv python install 3.12
uv venv .venv --python 3.12
uv sync --dev
uv run pytest
```

For local OpenAI runs, add your key to `.env`:

```bash
OPENAI_API_KEY=...
```

The key is loaded automatically for local development and is never written to benchmark artifacts.

## Commands

Generate a sample set:

```bash
uv run ui-bench generate --split train --difficulty easy --count 2 --seed 21
```

Render a DSL program:

```bash
uv run ui-bench render --program-file sample.dsl --output-file sample.png
```

Evaluate a predicted program directly:

```bash
uv run ui-bench eval --target-image target.png --prediction-file prediction.dsl
```

Run a model over a generated dataset. `--provider` selects one of `openai`,
`codex`, `heuristic`, or `empty`:

```bash
# Via the OpenAI API (burns API tokens)
uv run ui-bench run \
  --dataset-dir data/generated/train \
  --provider openai \
  --model gpt-5.4-nano-2026-03-17 \
  --reasoning-effort low \
  --image-detail low \
  --max-output-tokens 256 \
  --limit 2

# Via the Codex CLI (uses the ChatGPT login, no API tokens)
uv run ui-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider codex \
  --codex-model gpt-5.4 \
  --codex-timeout-seconds 240 \
  --limit 2

# Classical-CV baseline (no LLM, under a second for 150 samples)
uv run ui-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider heuristic
```

## Provider Defaults

Adapter defaults are kept conservative on cost.

**OpenAI Responses API** (`--provider openai`):

- default model: `gpt-5.4-nano-2026-03-17`
- `reasoning_effort`: `low`
- image `detail`: `low`
- `max_output_tokens`: `256`
- retry policy: none
- prompt mode: zero-shot only

**Codex CLI** (`--provider codex`):

- default model: `gpt-5.4`
- sandbox: `read-only`
- timeout: `180` seconds per sample
- retries: `2` with exponential backoff
- uses the ChatGPT login (no API tokens consumed)

Both LLM providers share a zero-shot prompt. The designed cost floor is small
personal-account smoke tests.

## DSL Example

```python
filled_circle(cx=128, cy=128, radius=40)
circle(cx=300, cy=220, radius=60, stroke=4)
filled_square(cx=220, cy=360, size=81)
square(cx=380, cy=120, size=80, stroke=3)
```

The evaluator accepts only a restricted subset of Python syntax:

- one top-level function call per line
- keyword arguments only
- integer literals only
- no imports, variables, expressions, loops, or arbitrary Python execution

## What The Repository Includes

- `src/ui_bench/dsl.py`: safe parser and canonical serializer
- `src/ui_bench/renderer.py`: deterministic Pillow renderer
- `src/ui_bench/generator.py`: seeded scene generation, sample writing, and a 2-sample smoke-test dataset helper
- `src/ui_bench/adapters/`: provider-agnostic adapter interface plus the OpenAI Responses API implementation
- `src/ui_bench/prompts.py`: fixed zero-shot benchmark prompt
- `src/ui_bench/normalization.py`: minimal response normalization
- `src/ui_bench/runner.py`: dataset loader, model runner, aggregation, and artifact writing
- `src/ui_bench/cli.py`: `generate`, `render`, `eval`, and `run` commands
- `tests/`: offline unit coverage plus an opt-in live OpenAI smoke test

Generated benchmark samples are written under `data/generated/<split>/<difficulty>/`.

Benchmark runs are written under `data/runs/<run_id>/` with:

- `run_config.json`
- `summary.json`
- `samples/<sample_id>.json`

## Cost-Safe Smoke Testing

Live API testing is explicit and intentionally tiny.

- Default `pytest` stays fully offline.
- The live smoke test is skipped unless `UI_BENCH_RUN_LIVE_OPENAI=1` is set.
- The live smoke path generates exactly 2 local examples: 1 `easy` and 1 `medium`.
- This is the recommended validation path while credits are limited.

## Why This Benchmark Is Useful

- It measures perception, spatial reasoning, and code generation together.
- It is fully synthetic, so large datasets can be generated cheaply.
- It supports controlled difficulty through size, overlap, clipping, and object count.
- It favors objective evaluation by comparing rendered outputs directly.
- It supports fresh held-out sets from new seeds, which reduces memorization of exact benchmark instances.

## Document Structure

- [README.md](README.md): project overview and implementation snapshot
- [paper/](paper/): arXiv paper source (LaTeX). Build with `cd paper && make`.
- [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md): end-to-end reproduction of the paper numbers
- [docs/benchmark-spec.md](docs/benchmark-spec.md): deeper implementation and benchmark spec
- [docs/research-landscape.md](docs/research-landscape.md): framework choice, related work, and positioning
- [AGENTS.md](AGENTS.md): repository guidance and project memory for coding agents

## Current Status

The V1 benchmark core, three provider adapters (OpenAI, Codex, and two non-LLM
baselines), the frozen `eval_v1` evaluation split, the analysis and figure
scripts, and the arXiv paper draft are all in place. See
[paper/main.tex](paper/main.tex) for the writeup and
[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for the end-to-end
reproduction workflow.

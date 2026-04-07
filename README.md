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

Generate a sample:

```bash
uv run ui-bench generate --split train --difficulty easy --count 1 --seed 21
```

Render a DSL program:

```bash
uv run ui-bench render --program-file sample.dsl --output-file sample.png
```

Evaluate a prediction:

```bash
uv run ui-bench eval --target-image target.png --prediction-file prediction.dsl
```

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
- `src/ui_bench/generator.py`: seeded scene generator for `easy`, `medium`, and `hard`
- `src/ui_bench/evaluator.py`: render-based scoring with exact match, pixel accuracy, and foreground IoU
- `src/ui_bench/cli.py`: `generate`, `render`, and `eval` commands
- `tests/`: parser, renderer, generator, evaluator, and CLI coverage

Generated samples are written under `data/generated/<split>/<difficulty>/` as paired PNG and JSON files.

## Why This Benchmark Is Useful

- It measures perception, spatial reasoning, and code generation together.
- It is fully synthetic, so large datasets can be generated cheaply.
- It supports controlled difficulty through size, overlap, clipping, and object count.
- It favors objective evaluation by comparing rendered outputs directly.
- It supports fresh held-out sets from new seeds, which reduces memorization of exact benchmark instances.

## Document Structure

- [README.md](README.md): project overview and implementation snapshot
- [docs/benchmark-spec.md](docs/benchmark-spec.md): deeper implementation and benchmark spec
- [docs/research-landscape.md](docs/research-landscape.md): framework choice, related work, and positioning
- [AGENTS.md](AGENTS.md): repository guidance and project memory for coding agents

## Current Status

The V1 benchmark core is implemented: environment setup, DSL parsing and serialization, renderer, generator, evaluator, CLI, and tests are in place.

The next recommended layer is model adapters and reporting on top of the current benchmark core.

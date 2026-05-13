# ShapeCodeBench

`ShapeCodeBench` is a synthetic benchmark for testing whether a multimodal model can look at an image and reconstruct the executable drawing program that generated it.

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

For local OpenAI Responses API runs, add your key to `.env`:

```bash
OPENAI_API_KEY=...
```

The key is loaded automatically for local development and is never written to benchmark artifacts.

For the two CLI-backed providers, install and authenticate the CLI directly — no API key is required, and no API tokens are consumed:

- **OpenAI Codex CLI** (`codex`): `codex login` (uses a ChatGPT subscription).
- **Claude Code CLI** (`claude`): `claude auth` (uses a Claude subscription).

## Commands

Generate a sample set:

```bash
uv run shape-code-bench generate --split train --difficulty easy --count 2 --seed 21
```

Render a DSL program:

```bash
uv run shape-code-bench render --program-file sample.dsl --output-file sample.png
```

Evaluate a predicted program directly:

```bash
uv run shape-code-bench eval --target-image target.png --prediction-file prediction.dsl
```

Run a model over a generated dataset. `--provider` selects one of `openai`,
`codex`, `claude`, `heuristic`, or `empty`:

```bash
# Via the OpenAI Responses API (burns API tokens)
uv run shape-code-bench run \
  --dataset-dir data/generated/train \
  --provider openai \
  --model gpt-5.5 \
  --reasoning-effort low \
  --image-detail low \
  --max-output-tokens 256 \
  --limit 2

# Via the OpenAI Codex CLI (uses the ChatGPT login, no API tokens)
uv run shape-code-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider codex \
  --codex-model gpt-5.5 \
  --codex-reasoning-effort medium \
  --codex-timeout-seconds 240 \
  --limit 2

# Via the Claude Code CLI (uses the Claude subscription, no API tokens)
uv run shape-code-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider claude \
  --claude-model 'claude-opus-4-7[1m]' \
  --claude-effort high \
  --claude-timeout-seconds 240 \
  --limit 2

# Classical-CV baseline (no LLM, under a second for 150 samples)
uv run shape-code-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider heuristic
```

## Provider Defaults

Adapter defaults are kept conservative on cost.

**OpenAI Responses API** (`--provider openai`):

- default model: `gpt-5.5`
- `reasoning_effort`: `low`
- image `detail`: `low`
- `max_output_tokens`: `256`
- retry policy: none
- prompt mode: zero-shot only

**OpenAI Codex CLI** (`--provider codex`):

- default model: `gpt-5.5`
- sandbox: `read-only`
- timeout: `180` seconds per sample
- retries: `2` with exponential backoff
- `--codex-reasoning-effort {low,medium,high,extra_high}`: unset by default;
  when set, threaded as `-c reasoning_effort=<value>` to `codex exec`
- uses the ChatGPT login (no API tokens consumed)

**Claude Code CLI** (`--provider claude`):

- default model: `claude-opus-4-7[1m]`
- `--claude-effort {low,medium,high,xhigh,max}`: defaults to `medium`
- timeout: `240` seconds per sample
- retries: `2` with exponential backoff
- ephemeral session via `--no-session-persistence`; the target image is attached
  via Claude Code's `@<path>` file-reference syntax, with `--add-dir` granting
  read access to the sample's directory
- uses the Claude subscription (no API tokens consumed)

All three LLM providers share a zero-shot prompt. The designed cost floor is
small personal-account smoke tests.

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

- `src/shape_code_bench/dsl.py`: safe parser and canonical serializer
- `src/shape_code_bench/renderer.py`: deterministic Pillow renderer
- `src/shape_code_bench/generator.py`: seeded scene generation, sample writing, and a 2-sample smoke-test dataset helper
- `src/shape_code_bench/adapters/`: provider-agnostic adapter interface plus three LLM-relevant implementations (OpenAI Responses API, OpenAI Codex CLI, Claude Code CLI)
- `src/shape_code_bench/prompts.py`: fixed zero-shot benchmark prompt
- `src/shape_code_bench/normalization.py`: minimal response normalization
- `src/shape_code_bench/runner.py`: dataset loader, model runner, aggregation, and artifact writing
- `src/shape_code_bench/cli.py`: `generate`, `render`, `eval`, and `run` commands
- `tests/`: offline unit coverage plus opt-in live smoke tests for the OpenAI Responses API and the Codex CLI

Generated benchmark samples are written under `data/generated/<split>/<difficulty>/`.

Benchmark runs are written under `data/runs/<run_id>/` with:

- `run_config.json`
- `summary.json`
- `samples/<sample_id>.json`

## Cost-Safe Smoke Testing

Live API testing is explicit and intentionally tiny.

- Default `pytest` stays fully offline.
- The live smoke test is skipped unless `SHAPE_CODE_BENCH_RUN_LIVE_OPENAI=1` is set.
- The live smoke path generates exactly 2 local examples: 1 `easy` and 1 `medium`.
- This is the recommended validation path while credits are limited.

## Why This Benchmark Is Useful

- It measures perception, spatial reasoning, and code generation together.
- It is fully synthetic, so large datasets can be generated cheaply.
- It supports controlled difficulty through size, overlap, clipping, and object count.
- It favors objective evaluation by comparing rendered outputs directly.
- It supports fresh held-out sets from new seeds, which reduces memorization of exact benchmark instances.
- It turns dataset refresh plus automatic scoring into a fast feedback loop for model, prompt, and adapter iteration without per-instance human annotation or manual judging.

## Evaluation Hygiene And Training Use

`eval_v1` is the frozen reporting split. Do not tune prompts, adapters, model
checkpoints, heuristic parameters, or difficulty settings on `eval_v1` and then
report the result as a clean held-out evaluation.

For development, generate separate train/dev splits from fresh seeds. Fresh
seeds reduce exact-instance contamination, but they do not prevent a model from
learning the overall generator distribution.

The current repository is an evaluation harness, not a training pipeline or a
differentiable pretraining loss. Future training use could pair generated images
with canonical DSL programs for supervised fine-tuning, or use parse/render
feedback as a verifiable reward for RL-style training. Those uses should keep
training seeds separate from frozen or newly minted held-out evaluation splits.

## Document Structure

- [README.md](README.md): project overview and implementation snapshot
- [paper/](paper/): arXiv paper source (LaTeX). Build with `cd paper && make`.
- [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md): end-to-end reproduction of the paper numbers
- [docs/benchmark-spec.md](docs/benchmark-spec.md): deeper implementation and benchmark spec
- [docs/research-landscape.md](docs/research-landscape.md): framework choice, related work, and positioning
- [AGENTS.md](AGENTS.md): repository guidance and project memory for coding agents

## Citation And Licensing

If you use ShapeCodeBench, cite the arXiv paper and the archived release. The
repository includes [CITATION.cff](CITATION.cff) for citation metadata and
[.zenodo.json](.zenodo.json) for Zenodo release metadata.

Paper: <https://arxiv.org/abs/2605.11680> (`arXiv:2605.11680`).
Archived release DOI: <https://doi.org/10.5281/zenodo.20132286>.

```bibtex
@misc{kumar2026shapecodebench,
  title = {ShapeCodeBench: A Renewable Benchmark for Perception-to-Program Reconstruction of Synthetic Shape Scenes},
  author = {Kumar, Shivam},
  year = {2026},
  eprint = {2605.11680},
  archivePrefix = {arXiv},
  primaryClass = {cs.CV},
  url = {https://arxiv.org/abs/2605.11680}
}
```

Source code is licensed under the MIT License in [LICENSE](LICENSE). Paper
source, documentation, generated benchmark datasets, figures, tables, and
benchmark run artifacts are licensed under CC BY 4.0 as described in
[LICENSE-ARTIFACTS.md](LICENSE-ARTIFACTS.md).

Some preserved run artifacts were produced before the public project rename and
may contain historical `ui-bench` prompt text. Those strings refer to the same
benchmark DSL now named ShapeCodeBench and are kept only to preserve the exact
recorded run configuration.

## Agent Context

`AGENTS.md` is the root operating guide and canonical source of shared
instructions for AI agents working in this repository.

Portable agent assets live under `.agents/`: reusable workflows in
`.agents/skills/` and saved prompt templates in `.agents/commands/`. The
`.claude/`, `.cursor/`, and `.codex/` directories are thin compatibility layers
that symlink to those shared assets; Codex-only environment setup belongs under
`.codex/environments/`.

## Current Status

The V1 benchmark core, three LLM provider adapters (OpenAI Responses API, OpenAI
Codex CLI, Claude Code CLI) plus two non-LLM baselines (empty-program floor,
classical-CV heuristic), the frozen `eval_v1` evaluation split, the analysis
and figure scripts, and the arXiv v1 paper are all in place. The paper's
canonical four-config baseline -- Claude Opus 4.7 (1M context) at `high` /
`max` effort and GPT-5.5 at `medium` / `extra_high` reasoning effort -- is
reproduced by `scripts/run_paper_sweep.sh`. See [paper/main.tex](paper/main.tex)
for the writeup and [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for the
end-to-end reproduction workflow.

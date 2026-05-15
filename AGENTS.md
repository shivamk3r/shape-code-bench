# AGENTS.md

This is the canonical operating guide for any AI agent working on `ShapeCodeBench`.
Keep shared agent behavior here. Product-specific files should be thin adapters
that point back to this file or to `.agents/`.

## Project Purpose

`ShapeCodeBench` is a synthetic multimodal benchmark for testing whether a model can
look at an image and reconstruct the executable drawing program that generated
it.

Core benchmark loop:

1. Generate a scene made of simple geometric primitives.
2. Convert that scene into canonical code in the benchmark DSL.
3. Render the image at `512x512`.
4. Ask a model to observe the image and write code in the same DSL.
5. Parse and execute the predicted program safely.
6. Render the prediction and compare it with the original image.

The main benchmark question is:

> Can a model infer the underlying program for a rendered synthetic scene well
> enough to reproduce the same output?

## Why This Project Matters

- It measures visual understanding and structured code generation together.
- It is fully synthetic, so large datasets can be generated cheaply.
- It supports difficulty-controlled evaluation through easy, medium, and hard
  tiers.
- It favors objective scoring by comparing rendered outputs.
- It can generate fresh held-out examples on demand, which reduces dependence
  on a permanently fixed public dataset.

## Contamination Resistance

One of the strongest advantages of `ShapeCodeBench` is contamination resistance at the
instance level.

If a released batch of examples becomes known or contaminated, the project can
generate a brand-new evaluation set from fresh seeds. This helps reduce
memorization of exact benchmark instances and keeps evaluation useful over time.

Important nuance:

- This reduces contamination of exact examples.
- It does not fully prevent models from learning the overall generator
  distribution.
- Hidden seeds and periodic refreshes still matter.

## Read First

Before making a substantial change, load context in this order:

1. `README.md` for the public overview, quickstart, commands, and current
   status.
2. `docs/benchmark-spec.md` for normative DSL, rendering, generation,
   evaluation, adapter, and artifact semantics.
3. The relevant implementation files under `src/shape_code_bench/`.
4. The matching tests under `tests/`.
5. This `AGENTS.md` for repository memory and shared agent behavior.

Do not treat backlog notes, scratch plans, or old run artifacts as live
instructions unless the user explicitly invokes them.

## Important Paths

- `src/shape_code_bench/dsl.py`: restricted parser and canonical serializer
- `src/shape_code_bench/renderer.py`: deterministic Pillow renderer
- `src/shape_code_bench/generator.py`: seeded scene generation and sample metadata
- `src/shape_code_bench/evaluator.py`: render-based scoring
- `src/shape_code_bench/prompts.py`: fixed zero-shot benchmark prompt
- `src/shape_code_bench/normalization.py`: minimal model-output normalization
- `src/shape_code_bench/runner.py`: dataset loading, model execution, aggregation, and
  run artifacts
- `src/shape_code_bench/adapters/`: provider-agnostic adapters for OpenAI Responses API,
  OpenAI Codex CLI, Claude Code CLI, and baselines
- `src/shape_code_bench/cli.py`: `generate`, `render`, `eval`, and `run`
- `tests/`: offline unit coverage plus opt-in live smoke tests
- `docs/`: benchmark specification, reproducibility notes, and research context
- `paper/`: arXiv paper source and build files
- `scripts/`: analysis, determinism, figure, evaluation-freezing, and paper
  sweep helpers
- `publish_docs/`: git-ignored private publishing drafts, notes, and prep work

Generated samples go under `data/generated/<split>/<difficulty>/`.
Benchmark run outputs go under `data/runs/<run_id>/`.
The public Hugging Face mirror for the frozen `eval_v1` dataset is
<https://huggingface.co/datasets/shivamk3r/shape-code-bench-eval-v1>.

## Current V1 Decisions

Unless explicitly updated in the source-of-truth documents, assume:

- Canvas size is fixed at `512x512`.
- V1 primitives are `circle`, `filled_circle`, `square`, and `filled_square`.
- The initial palette is black shapes on a white background.
- Rendering must be deterministic.
- Program order is preserved, but under the black-on-white V1 palette
  overlapping shapes are effectively order-invariant in the final raster.
- The benchmark uses a project-owned Python-like DSL.
- The evaluator must parse a restricted subset instead of executing arbitrary
  Python.
- Primary scoring is render-based, not exact code-string match.
- V1 ships with `easy`, `medium`, and `hard` difficulty tiers.
- The implemented stack is Python `3.12` with `uv`, a local `.venv`, `Pillow`,
  `numpy`, the OpenAI Python SDK, `python-dotenv`, `pytest`, and `ruff`.
- The model runner uses a provider-agnostic adapter interface with OpenAI
  Responses API, OpenAI Codex CLI (`codex exec`), Claude Code CLI
  (`claude --print`), and baseline implementations.
- Default low-cost OpenAI smoke-test settings are `gpt-5.5`,
  `reasoning_effort="low"`, image `detail="low"`, `max_output_tokens=256`, and
  no retry.
- Default Codex CLI settings are `gpt-5.5` with sandbox `read-only`, timeout
  `180s`, and `2` retries; effort is unset by default and threaded via
  `--codex-reasoning-effort`.
- Default Claude Code CLI settings are `claude-opus-4-7[1m]` with effort
  `medium`, timeout `240s`, and `2` retries; effort is one of
  `low|medium|high|xhigh|max`.
- Live API/CLI testing remains opt-in and capped at 2 examples unless the user
  explicitly requests a larger run.

## Source Of Truth And Recency

Keep these documents aligned:

- `README.md` for the public project overview and implementation snapshot
- `docs/benchmark-spec.md` for deeper benchmark and implementation semantics
- `AGENTS.md` for repository-wide agent instructions and project memory

When source and docs disagree, prefer executable code and tests for current
behavior, then update the docs if the behavior is intentional. For policy,
workflow, or collaboration rules, prefer this file.

Update `AGENTS.md` whenever any of these change:

- benchmark task definition
- DSL surface area
- evaluation metrics or scoring policy
- dataset generation strategy
- difficulty-tier definitions
- repository structure
- major workflow or tooling decisions
- shared agent asset layout

Before finishing a substantial change, do a freshness check:

- Does `README.md` still describe the project accurately?
- Does `docs/benchmark-spec.md` still match the implementation?
- Should `AGENTS.md` be updated so future agents inherit the latest decisions?

## Privacy And Sensitivity

- Do not commit secrets, API keys, credentials, local tokens, or personal account
  state.
- `.env` is for local development only. The OpenAI key is loaded automatically
  when present and must never be written to benchmark artifacts.
- CLI adapters use the user's authenticated `codex` or `claude` sessions. Do
  not expose, copy, or persist authentication material.
- Treat generated model outputs and benchmark run artifacts as potentially
  sensitive until the user says they are safe to publish.
- Keep live API/CLI runs opt-in, small, and explicit because they may consume
  credits, subscription quota, or local authenticated sessions.
- `publish_docs/` is intentionally git ignored. Agents may create or use it for
  private publishing drafts, notes, and prep work, but its contents must not be
  committed or treated as public project documentation. If the directory is
  missing, agents may recreate it locally.

## Coding And Editing Conventions

- Preserve the benchmark's focus on perception-to-program reconstruction.
- Keep the DSL intentionally small in V1.
- Prefer deterministic behavior everywhere: generation, rendering, parsing,
  scoring, tests, and scripts.
- Treat image-level equivalence as more important than textual code equivalence.
- Avoid features that make the task depend on graphics-library trivia instead
  of visual reasoning.
- Use the project-owned DSL and restricted parser; never execute arbitrary
  model-produced code.
- Prefer small, focused changes that match existing style and test structure.
- Use `uv` for project commands.
- Preserve unrelated user changes. Do not rewrite generated data, paper
  artifacts, or cached files unless the task requires it.
- Keep portable agent instructions product-neutral. Put product-specific setup
  only in the adapter folders described below.

## Safety And Evaluation Guardrails

- Do not execute arbitrary model-produced code.
- Prefer restricted parsing and validated dispatch into approved drawing
  operations.
- Keep outputs reproducible from seeds.
- Log enough metadata to reproduce a sample and an evaluation run.
- Start simple before expanding to colors, rotation, or more complex shapes.

## Verification Expectations

Default verification should be offline and deterministic:

```bash
uv run pytest
uv run ruff check .
```

Run narrower tests when the change is scoped, and broaden verification when a
change touches shared behavior, scoring, adapters, or CLI workflows.

Live smoke tests are skipped by default and must stay explicit:

- `SHAPE_CODE_BENCH_RUN_LIVE_OPENAI=1`
- `SHAPE_CODE_BENCH_RUN_LIVE_CODEX=1`

Do not run live API/CLI evaluation over more than 2 examples unless the user
explicitly asks for a larger run.

For agent-file changes, also run:

```bash
for p in CLAUDE.md .claude/skills .claude/commands .cursor/skills .cursor/commands .codex/skills; do printf '%s -> %s\n' "$p" "$(readlink "$p")"; done
git diff --check
git status --short
```

## Agent Assets

Portable shared assets live under `.agents/`:

- `.agents/skills/<skill-name>/SKILL.md`: reusable task workflows with context,
  steps, output contract, and verification requirements.
- `.agents/skills/<skill-name>/references/`: optional supporting docs for that
  skill.
- `.agents/skills/<skill-name>/scripts/`: optional helper scripts for that
  skill.
- `.agents/commands/<command-name>.md`: lightweight reusable prompts or
  slash-command templates.

Skills and commands in `.agents/` must be product-neutral and usable by Claude,
Cursor, Codex, or other agents. Do not place platform-specific metadata inside
portable skills unless the user explicitly requests it.

## Tool Compatibility Folders

Tool-specific folders are adapters, not sources of truth:

- `CLAUDE.md` should be a symlink to `AGENTS.md`.
- `.claude/skills` should symlink to `../.agents/skills`.
- `.claude/commands` should symlink to `../.agents/commands`.
- `.cursor/skills` should symlink to `../.agents/skills`.
- `.cursor/commands` should symlink to `../.agents/commands`.
- `.codex/skills` should symlink to `../.agents/skills`.

Do not duplicate shared skills or commands inside tool-specific folders.

Codex-only setup belongs under `.codex/environments/`, for example:

- `.codex/environments/environment.toml`
- `.codex/environments/setup-worktree.sh`
- `.codex/environments/cleanup-worktree.sh`

Do not create `.codex/commands` unless this repository explicitly needs a
Codex-only command layer.

## Near-Term Build Order

The benchmark core and live runners are implemented. The recommended next
order is:

1. Add richer reporting and per-slice benchmark diagnostics.
2. Validate the current zero-shot baseline empirically on small pilot runs.
3. Add more providers or prompt regimes only after the baseline is
   characterized.
4. Expand the DSL only after the V1 core is stable and benchmarked.

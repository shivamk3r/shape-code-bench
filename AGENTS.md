# AGENTS.md

This file contains repository-wide instructions for any coding agent working on `ui-bench`.

Treat this as a living project guide. Keep it current as the benchmark evolves so future agents inherit the latest project context, decisions, and working expectations.

## Project Mission

`ui-bench` is a synthetic multimodal benchmark for testing whether a model can look at an image and reconstruct the executable drawing program that generated it.

Core benchmark loop:

1. Generate a scene made of simple geometric primitives.
2. Convert that scene into canonical code in the benchmark DSL.
3. Render the image at `512x512`.
4. Ask a model to observe the image and write code in the same DSL.
5. Parse and execute the predicted program safely.
6. Render the prediction and compare it with the original image.

The main benchmark question is:

> Can a model infer the underlying program for a rendered synthetic scene well enough to reproduce the same output?

## Why This Project Matters

- It measures visual understanding and structured code generation together.
- It is fully synthetic, so large datasets can be generated cheaply.
- It supports difficulty-controlled evaluation through easy, medium, and hard tiers.
- It favors objective scoring by comparing rendered outputs.
- It can generate fresh held-out examples on demand, which reduces dependence on a permanently fixed public dataset.

## Main USP

One of the strongest advantages of `ui-bench` is contamination resistance at the instance level.

If a released batch of examples becomes known or contaminated, the project can generate a brand-new evaluation set from fresh seeds. This helps reduce memorization of exact benchmark instances and keeps evaluation useful over time.

Important nuance:

- This reduces contamination of exact examples.
- It does not fully prevent models from learning the overall generator distribution.
- Hidden seeds and periodic refreshes still matter.

## Current V1 Decisions

Unless explicitly updated elsewhere in the repository, assume the following:

- Canvas size is fixed at `512x512`.
- V1 primitives are `circle`, `filled_circle`, `square`, and `filled_square`.
- The initial palette is black shapes on a white background.
- Rendering must be deterministic.
- Program order is preserved, but under the black-on-white V1 palette overlapping shapes are effectively order-invariant in the final raster.
- The benchmark should use a project-owned DSL rather than an external drawing framework.
- The syntax may look Python-like, but the evaluator must parse a restricted subset instead of executing arbitrary Python.
- Primary scoring is render-based, not exact code-string match.
- V1 should ship with `easy`, `medium`, and `hard` difficulty tiers.
- The implemented stack is Python `3.12` with `uv`, a local `.venv`, `Pillow`, `numpy`, `pytest`, and `ruff`.

## Current Repository Structure

The current implementation lives in:

- `src/ui_bench/dsl.py` for parsing and canonical serialization
- `src/ui_bench/renderer.py` for deterministic raster rendering
- `src/ui_bench/generator.py` for seeded scene generation and sample metadata
- `src/ui_bench/evaluator.py` for render-based scoring
- `src/ui_bench/cli.py` for `generate`, `render`, and `eval`
- `tests/` for parser, renderer, generator, evaluator, and CLI coverage

Generated outputs should go under `data/generated/<split>/<difficulty>/`.

## Agent Working Principles

- Preserve the benchmark's focus on perception-to-program reconstruction.
- Keep the DSL intentionally small in V1.
- Prefer deterministic behavior everywhere: generation, rendering, parsing, and scoring.
- Treat image-level equivalence as more important than textual code equivalence.
- Avoid adding features that make the task depend on library trivia instead of visual reasoning.
- When making implementation decisions, optimize for benchmark credibility, reproducibility, and clean evaluation.

## Safety And Evaluation Guardrails

- Do not execute arbitrary model-produced code.
- Prefer restricted parsing and validated dispatch into approved drawing operations.
- Keep outputs reproducible from seeds.
- Log enough metadata to reproduce a sample and an evaluation run.
- Start simple before expanding to colors, rotation, or more complex shapes.

## Source Of Truth

When working in this repository, keep these documents aligned:

- `README.md` for the public project overview
- `docs/benchmark-spec.md` for the deeper benchmark and implementation spec
- `AGENTS.md` for repository-wide agent instructions and project memory

If one of these changes in a meaningful way, check whether the others should be updated too.

## Documentation Responsibilities

Update `AGENTS.md` whenever any of the following changes:

- The benchmark task definition
- The DSL surface area
- Evaluation metrics or scoring policy
- Dataset generation strategy
- Difficulty-tier definitions
- Repository structure
- Major workflow or tooling decisions

## Near-Term Build Order

The benchmark core is implemented. The current recommended next order is:

1. Add model adapters on top of the existing evaluator.
2. Add reporting and aggregate benchmark summaries.
3. Validate the current difficulty tiers empirically.
4. Expand the DSL only after the V1 core is stable and benchmarked.

## Freshness Check For Agents

Before finishing any substantial change, quickly check:

- Does `README.md` still describe the project accurately?
- Does `docs/benchmark-spec.md` still match the implementation plan?
- Should `AGENTS.md` be updated so future agents inherit the latest decisions?

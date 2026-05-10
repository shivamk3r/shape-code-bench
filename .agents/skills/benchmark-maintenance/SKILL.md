---
name: benchmark-maintenance
description: Safely modify ui-bench benchmark behavior, documentation, tests, or provider adapters while preserving deterministic evaluation.
---

# Benchmark Maintenance

## When To Use

Use this skill for changes that affect the benchmark task, DSL, renderer,
generator, evaluator, adapters, CLI, docs, or paper/reproducibility workflow.

## Context To Load

- `AGENTS.md`
- `README.md`
- `docs/benchmark-spec.md`
- The relevant files under `src/ui_bench/`
- The matching tests under `tests/`
- `docs/REPRODUCIBILITY.md` when paper numbers, frozen evaluation, or live runs
  are involved

## Workflow

1. Identify whether the requested change affects benchmark semantics, tooling,
   docs, or artifacts.
2. Read the implementation and tests that define the current behavior before
   editing.
3. Keep the DSL and evaluation path deterministic and restricted; never execute
   arbitrary model-produced code.
4. Make the smallest coherent code or documentation change that matches existing
   project patterns.
5. Update `README.md`, `docs/benchmark-spec.md`, and `AGENTS.md` if the change
   alters public behavior, source-of-truth decisions, or agent workflow.
6. Avoid touching generated data, run outputs, cached files, paper build
   artifacts, or unrelated user changes unless the task explicitly requires it.

## Output Contract

Return a concise summary of:

- What changed
- Which files changed
- What verification was run
- Any tests or live checks intentionally skipped
- Any source-of-truth documents that were checked or updated

## Verification

Prefer deterministic offline checks:

```bash
uv run pytest
uv run ruff check .
```

Run narrower tests for scoped changes and broader tests for changes touching
shared benchmark semantics. Live API/CLI smoke tests must remain explicit and
capped at 2 examples unless the user asks for more.

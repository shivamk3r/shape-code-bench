# Reproducing `ui-bench` Experiments

This guide reproduces the headline numbers, figures, and paper PDF from a clean
checkout of `ui-bench`. Everything here is deterministic up to each CLI's
per-call sampling; see [Limitations](#8-limitations-and-caveats) below.

## 1. Environment

- macOS or Linux with `bash`.
- Python 3.12 (pinned in `.python-version`).
- [`uv`](https://docs.astral.sh/uv/) 0.4 or newer.
- The OpenAI Codex CLI, `codex` >= 0.121.0, on `$PATH`.
- The Claude Code CLI, `claude` >= 2.1, on `$PATH`.
- TeX Live 2024+ (needs `pdflatex` and `bibtex`) — only required for the paper
  build, not for running the benchmark.

Install Python deps:

```bash
uv python install 3.12
uv venv .venv --python 3.12
uv sync --dev
```

## 2. CLI logins

Both CLI-backed adapters authenticate via subscription rather than an API key —
no API tokens are consumed on either path.

### Codex CLI (ChatGPT subscription)

```bash
codex login          # opens a browser to complete ChatGPT login
codex login status   # should print "Logged in using ChatGPT"
```

Verify the GPT-5.5 model is available on your account at `medium` and
`extra_high` reasoning effort:

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only \
  -m gpt-5.5 -c reasoning_effort=medium --color never "Reply with OK"
codex exec --skip-git-repo-check --ephemeral -s read-only \
  -m gpt-5.5 -c reasoning_effort=extra_high --color never "Reply with OK"
```

If a reasoning-effort value is rejected by your CLI version, the adapter falls
back to that error in the per-sample artifact; drop the affected configuration
or substitute a documented value (`low|medium|high`).

### Claude Code CLI (Claude subscription)

```bash
claude auth          # opens a browser to complete Claude login
claude --version     # should print 2.1.x
```

Verify Claude Opus 4.7 (1M context) is reachable at both target effort levels:

```bash
claude --print --add-dir . --model 'claude-opus-4-7[1m]' --effort high \
  --output-format text --no-session-persistence "Reply with OK"
claude --print --add-dir . --model 'claude-opus-4-7[1m]' --effort max \
  --output-format text --no-session-persistence "Reply with OK"
```

## 3. Regenerate the evaluation dataset

`eval_v1` is 150 samples produced from seeds `0..49` per difficulty tier.
Regenerating is deterministic and takes under a second:

```bash
uv run python scripts/freeze_eval_v1.py
```

This writes images and per-sample metadata under `data/eval_v1/eval/<difficulty>/`,
a `manifest.json` with the generator commit SHA, and a `SHA256SUMS` file over
every PNG. To verify that your regenerated dataset is bit-identical to the
checked-in reference:

```bash
cd data/eval_v1 && shasum -a 256 -c SHA256SUMS | tail -3
```

Every line should read `OK`.

## 4. Run all sweeps

Run the two non-LLM baselines first; they complete in under a second:

```bash
uv run ui-bench run --dataset-dir data/eval_v1/eval --provider empty     --output-dir data/runs
uv run ui-bench run --dataset-dir data/eval_v1/eval --provider heuristic --output-dir data/runs
```

Then run the four CLI-backed multimodal sweeps. This step dominates the
wall-clock time (~10–30 seconds per sample on a Pro / Claude subscription at
the time of writing, so roughly 25–75 minutes per configuration). A
convenience script runs the full set serially:

```bash
bash scripts/run_paper_sweep.sh
```

The script iterates over the four canonical paper configurations:

- `claude-opus-4-7[1m]` at `--claude-effort high`
- `claude-opus-4-7[1m]` at `--claude-effort max`
- `gpt-5.5` at `--codex-reasoning-effort medium`
- `gpt-5.5` at `--codex-reasoning-effort extra_high`

and writes each run under `data/runs/<timestamp>-<provider>-<model-slug>/`.
The committed sweep script uses the same per-sample timeout budgets as the
checked-in paper artifacts: 1800 seconds for the `high`/`medium` runs and 2400
seconds for the `max`/`extra_high` runs.

Every run directory contains:

- `run_config.json` — frozen adapter config (including the effort level), dataset path, selected sample IDs.
- `summary.json` — aggregated metrics, including per-tier breakdowns.
- `samples/*.json` — one file per sample, with request, raw and normalized
  predictions, and the full evaluation result.

If you would rather parallelize across providers (Claude track and Codex track
share no rate-limit account), launch each as its own background bash; runs
within the same provider should stay serial to minimize contention on the same
subscription.

## 5. Tables and figures

Once all runs are written, regenerate the paper tables and figures:

```bash
uv run python scripts/analyze.py        # writes paper/tables/*.{csv,tex}
uv run python scripts/make_figures.py   # writes paper/figures/*.pdf
```

Both scripts are idempotent and safe to rerun after adding additional runs.
Multi-effort runs of the same model are disambiguated automatically in tables
and figures (e.g. `claude-opus-4-7[1m] (high)` vs `claude-opus-4-7[1m] (max)`).
Old run directories that are not part of the current canonical baseline can be
moved under `data/runs/archived/` to keep them out of figure regeneration
without losing the artifacts.

## 6. Paper PDF

```bash
cd paper && make
```

This runs `pdflatex` + `bibtex` + `pdflatex` + `pdflatex`. The output is
`paper/main.pdf`.

To build the arXiv submission tarball (which bundles the `.bbl` because arXiv
does not run BibTeX):

```bash
cd paper && make arxiv
```

## 7. Tests

Offline tests (no Codex, Claude Code, or OpenAI API calls):

```bash
uv run pytest
```

Live Codex smoke test (one easy + one medium sample through real Codex):

```bash
UI_BENCH_RUN_LIVE_CODEX=1 uv run pytest tests/test_live_codex_smoke.py -v
```

You may override the model used for the Codex smoke test by setting
`UI_BENCH_CODEX_SMOKE_MODEL` (default: `gpt-5.5`).

Live OpenAI Responses API smoke test (requires `OPENAI_API_KEY`):

```bash
UI_BENCH_RUN_LIVE_OPENAI=1 uv run pytest tests/test_live_openai_smoke.py -v
```

There is no live Claude Code smoke test today; validate the Claude path with
a `--limit 2` run instead:

```bash
uv run ui-bench run \
  --dataset-dir data/eval_v1/eval \
  --provider claude \
  --claude-model 'claude-opus-4-7[1m]' \
  --claude-effort high \
  --limit 2
```

## 8. Limitations and caveats

- **CLI sampling non-determinism.** Neither the OpenAI Codex CLI nor the Claude
  Code CLI exposes a seed for the underlying model, so two identical requests
  can produce different predictions. Each run's `run_config.json` captures the
  model identifier, the effort level, and the adapter settings used at
  invocation time. We cannot guarantee bit-exact reproduction of reported
  numbers; the renewable design of `ui-bench` mitigates this — re-running
  either CLI on the same `eval_v1` seeds reproduces the *experimental setup*
  faithfully even when individual predictions vary.
- **CLI versions used.** The four sweeps reported in the paper were run on
  whatever Codex CLI and Claude Code CLI versions were installed on the
  author's machine at sweep time; the exact binary versions are not pinned in
  the run artifacts. To document your own environment, capture
  `codex --version` and `claude --version` alongside your run output. The
  adapter argv shape is documented in
  `src/ui_bench/adapters/codex_adapter.py` and
  `src/ui_bench/adapters/claude_code_adapter.py`.
- **Subscription quotas.** Running the full four-config sweep consumes a
  meaningful portion of daily ChatGPT Pro usage (Codex track) and a meaningful
  portion of Claude subscription budget (Claude track). If a sweep stalls on
  quota, the convenience script continues with the next configuration and
  partial run directories are still analyzable.
- **Model access.** Available models depend on the subscription tier at run
  time. If `gpt-5.5` is not exposed on your ChatGPT account, or if
  `claude-opus-4-7[1m]` is unavailable on yours, report the subset you actually
  ran rather than substituting silently.
- **Dataset versioning.** Any change to the generator logic invalidates
  `eval_v1`. If you revise generator behavior, bump to `eval_v2` and record the
  generator commit SHA in the new manifest.

## 9. Questions?

Open an issue on the project repository with the relevant `run_config.json`
and the tail of `summary.json` attached, plus the output of
`codex --version`, `claude --version`, and `uv --version`.

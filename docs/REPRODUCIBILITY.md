# Reproducing `ui-bench` Experiments

This guide reproduces the headline numbers, figures, and paper PDF from a clean
checkout of `ui-bench`. Everything here is deterministic up to the Codex
CLI's per-call sampling; see [Limitations](#limitations-and-caveats) below.

## 1. Environment

- macOS or Linux with `bash`.
- Python 3.12 (pinned in `.python-version`).
- [`uv`](https://docs.astral.sh/uv/) 0.4 or newer.
- The OpenAI Codex CLI, `codex` >= 0.121.0, on `$PATH`.
- TeX Live 2024+ (needs `pdflatex` and `bibtex`) — only required for the paper
  build, not for running the benchmark.

Install Python deps:

```bash
uv python install 3.12
uv venv .venv --python 3.12
uv sync --dev
```

## 2. Codex CLI login

The Codex adapter uses `codex exec`, which authenticates via your ChatGPT login
rather than an API key. A ChatGPT Pro subscription is currently required for
the `gpt-5.4` / `gpt-5.3-codex` / `gpt-5.4-mini` models used in the paper.

```bash
codex login          # opens a browser to complete ChatGPT login
codex login status   # should print "Logged in using ChatGPT"
```

Verify the exact model IDs are available on your account:

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only \
  -m gpt-5.4 --color never "Reply with OK"
codex exec --skip-git-repo-check --ephemeral -s read-only \
  -m gpt-5.3-codex --color never "Reply with OK"
codex exec --skip-git-repo-check --ephemeral -s read-only \
  -m gpt-5.4-mini --color never "Reply with OK"
```

If a model rejects the request with "not supported when using Codex with a
ChatGPT account", drop that model from the sweep and note it in any tables you
derive from the run artifacts.

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

Then run the three Codex-backed multimodal sweeps. This step dominates the
wall-clock time (~30 seconds per sample on a Pro account at the time of writing,
so roughly 1 to 1.5 hours per model). A convenience script runs them serially:

```bash
bash scripts/run_codex_sweep.sh
```

The script iterates over `gpt-5.4`, `gpt-5.3-codex`, `gpt-5.4-mini` and writes
each run under `data/runs/<timestamp>-codex-<model>/`.

Every run directory contains:

- `run_config.json` — frozen adapter config, dataset path, selected sample IDs.
- `summary.json` — aggregated metrics, including per-tier breakdowns.
- `samples/*.json` — one file per sample, with request, raw and normalized
  predictions, and the full evaluation result.

## 5. Tables and figures

Once all runs are written, regenerate the paper tables and figures:

```bash
uv run python scripts/analyze.py        # writes paper/tables/*.{csv,tex}
uv run python scripts/make_figures.py   # writes paper/figures/*.pdf
```

Both scripts are idempotent and safe to rerun after adding additional runs.

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

Offline tests (no Codex or OpenAI API calls):

```bash
uv run pytest
```

Live Codex smoke test (one easy + one medium sample through real Codex):

```bash
UI_BENCH_RUN_LIVE_CODEX=1 uv run pytest tests/test_live_codex_smoke.py -v
```

You may override the model used for the smoke test by setting
`UI_BENCH_CODEX_SMOKE_MODEL` (default: `gpt-5.4`).

## 8. Limitations and caveats

- **Codex sampling non-determinism.** The Codex CLI does not expose a seed for
  the underlying model, so two identical requests can produce different
  predictions. We cannot guarantee bit-exact reproduction of reported numbers.
- **Codex CLI versions used.** The sweeps reported in the paper ran on Codex
  CLI `0.121.0` and `0.122.0` (stable). A minor version bump from `0.121.0`
  to `0.122.0` happened on the author's first machine between the `gpt-5.4`
  sweep and the first `gpt-5.4-mini` attempt, overlapping the `gpt-5.3-codex`
  sweep. The `gpt-5.4-mini` sweep was then completed from scratch on a second
  machine on pinned `0.122.0` (installed via `npm install -g
  @openai/codex@0.122.0`); the initial 110-sample partial run from the first
  machine was discarded. The adapter arguments and prompt were unchanged
  across versions.
- **Concurrent sweeps on the author's machine.** The `gpt-5.4-mini` sweep was
  launched in a parallel shell during the tail of the `gpt-5.3-codex` sweep to
  reduce wall-clock. Codex outcomes should be independent across sweeps (each
  `codex exec` is a separate ephemeral session under the same ChatGPT Pro
  login), but if an account-level rate limit briefly throttled the mini run,
  it would manifest as additional `timeout` or `process_failure` entries in
  the per-sample error taxonomy. The `run_codex_sweep.sh` script remains
  serial by default for clean reproduction.
- **ChatGPT account quotas.** Running the full sweep consumes a meaningful
  portion of daily ChatGPT Pro usage. If the sweep stalls on quota, the script
  will continue with the next model and partial run directories are still
  analyzable.
- **Model access.** Available Codex models depend on the subscription tier at
  run time. If `gpt-5.4-mini` or `gpt-5.3-codex` are not exposed on your
  account, report the subset of models you actually ran.
- **Dataset versioning.** Any change to the generator logic invalidates
  `eval_v1`. If you revise generator behavior, bump to `eval_v2` and record the
  generator commit SHA in the new manifest.

## 9. Questions?

Open an issue on the project repository with the relevant `run_config.json` and
the tail of `summary.json` attached, plus the output of `codex --version` and
`uv --version`.

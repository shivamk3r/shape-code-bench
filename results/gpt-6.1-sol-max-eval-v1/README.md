# GPT-6.1 Sol maximum-effort evaluation

On 2026-10-02, GPT-6.1 Sol reconstructed all 150 frozen `eval_v1` scenes through
Codex CLI at `max` reasoning effort, with a one-hour total budget per sample
and eight concurrent workers. The full run reused two verified pilot responses
and requested the other 148 samples. All predictions parsed and executed;
there were no adapter errors.

| Difficulty | Samples | Exact matches | Pixel accuracy | Foreground IoU | Mean request time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 150 | 28 / 150 (18.67%) | 99.62% | 93.84% | 96.83 s |
| Easy | 50 | 16 / 50 (32.00%) | 99.76% | 92.19% | 43.74 s |
| Medium | 50 | 6 / 50 (12.00%) | 99.54% | 92.96% | 88.15 s |
| Hard | 50 | 6 / 50 (12.00%) | 99.56% | 96.38% | 158.59 s |

Parse and execution success are 100% overall and in every tier. The overall
foreground-IoU 95% bootstrap interval is **91.77–95.65%**; the exact-match
interval is **12.67–24.67%**. All metric intervals use 1,000 resamples and seed
2026, matching the analysis helper's method. The full invocation took 31.26
minutes; the two-sample pilot took 68.30 seconds. Eight simultaneous Codex
sample processes were observed during the full run.

## Protocol and provenance

- Model: `gpt-6.1-sol`, via `codex-cli 0.160.0` and the authenticated ChatGPT login.
- Reasoning setting: explicit `-c model_reasoning_effort=max`.
- Timeout: 3,600 seconds total for a sample, including up to two retries and backoff.
- Prompt: the unchanged fixed zero-shot ShapeCodeBench DSL prompt.
- Inputs: `eval_v1`, seeds `0..49` in each of `easy`, `medium`, and `hard`.
- Pilot: `eval-easy-00000000` and `eval-medium-00000000`, using two workers.
- Full invocation: eight workers, two cached responses, 148 new sample requests.
- Each request uses an ephemeral temporary working directory containing a
  copied `input.png`; personal CLI configuration is disabled with
  `--ignore-user-config` while authentication is retained.
- Environment: Python 3.12.3, Pillow 11.3.0, NumPy 2.4.4.

The dataset, DSL, renderer, scoring, and prompt retain the V1 semantics.
Pilot validation checked transport and DSL validity; no prompt or scoring
tuning was performed. The current adapter fixes the Codex configuration key
and normalizes the legacy `extra_high` spelling to `xhigh`. Historical paper
results keep their original recorded effort labels; their effective Codex
effort was not independently verified, and this follow-up is presented
separately from the paper tables.

## Saved results

- [main_results.csv](main_results.csv): overall and tier metrics with 95% intervals.
- [sample_metrics.csv](sample_metrics.csv): all 150 sample scores, input hashes, and latencies.
- [summary.json](summary.json): aggregate scores, tier counts, and error counts.
- [protocol.json](protocol.json): settings, versions, source and dataset hashes,
  per-sample artifact hashes, concurrency observation, and both invocation records.

The raw predictions, CLI thread IDs, usage metadata, and full run configuration
are retained locally in the git-ignored directory:

```text
data/runs/gpt-6.1-sol-max-eval-v1/20261002T053633860976Z-codex-gpt-6-1-sol/
```

Re-export and verify the saved predictions without another model call:

```bash
uv run python scripts/report_run.py \
  --run-dir data/runs/gpt-6.1-sol-max-eval-v1/20261002T053633860976Z-codex-gpt-6-1-sol \
  --output-dir results/gpt-6.1-sol-max-eval-v1
```

The exporter requires a complete evaluation, checks input and prediction
integrity, recomputes every score through the restricted evaluator, and verifies
the aggregates. Repeated export from these artifacts is deterministic. Fresh
model predictions can vary; see the [reproduction guide](../../docs/REPRODUCIBILITY.md#11-gpt-61-sol-follow-up-evaluation)
for the pilot and full-run commands. Scores and protocol downloads are also
included in the project website build.

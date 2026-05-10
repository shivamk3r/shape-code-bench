#!/usr/bin/env bash
# Run the four canonical ui-bench paper baselines on the frozen eval_v1 dataset.
# Each invocation writes under data/runs/<run_id>/. A failure in one config
# does not abort the others.

set -u
set -o pipefail

DATASET_DIR="data/eval_v1/eval"
OUTPUT_DIR="data/runs"

CLAUDE_MODEL="claude-opus-4-7[1m]"
CODEX_MODEL="gpt-5.5"

# (label, provider, effort-flag, effort-value, timeout-seconds)
CONFIGS=(
  "claude-opus-4-7-1m@max|claude|--claude-effort|max|2400"
  "claude-opus-4-7-1m@high|claude|--claude-effort|high|1800"
  "gpt-5.5@extra_high|codex|--codex-reasoning-effort|extra_high|2400"
  "gpt-5.5@medium|codex|--codex-reasoning-effort|medium|1800"
)

for entry in "${CONFIGS[@]}"; do
  IFS="|" read -r label provider effort_flag effort_value timeout_seconds <<<"${entry}"

  echo "========================================================================"
  echo "[$(date -u +%H:%M:%SZ)] Starting sweep: ${label}"
  echo "========================================================================"

  if [[ "${provider}" == "claude" ]]; then
    uv run ui-bench run \
      --dataset-dir "${DATASET_DIR}" \
      --provider claude \
      --claude-model "${CLAUDE_MODEL}" \
      "${effort_flag}" "${effort_value}" \
      --claude-timeout-seconds "${timeout_seconds}" \
      --output-dir "${OUTPUT_DIR}" \
      || {
        echo "[$(date -u +%H:%M:%SZ)] sweep ${label} exited non-zero; continuing"
      }
  else
    uv run ui-bench run \
      --dataset-dir "${DATASET_DIR}" \
      --provider codex \
      --codex-model "${CODEX_MODEL}" \
      "${effort_flag}" "${effort_value}" \
      --codex-timeout-seconds "${timeout_seconds}" \
      --output-dir "${OUTPUT_DIR}" \
      || {
        echo "[$(date -u +%H:%M:%SZ)] sweep ${label} exited non-zero; continuing"
      }
  fi

  echo "[$(date -u +%H:%M:%SZ)] Finished sweep: ${label}"
done

echo "========================================================================"
echo "[$(date -u +%H:%M:%SZ)] All paper sweeps complete."
echo "========================================================================"

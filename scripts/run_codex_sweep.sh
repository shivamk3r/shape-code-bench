#!/usr/bin/env bash
# Serially runs all three Codex sweeps on the frozen eval_v1 dataset.
# Each run writes under data/runs/<run_id>/. Progress streams to stdout.

set -u
set -o pipefail

MODELS=("gpt-5.4" "gpt-5.3-codex" "gpt-5.4-mini")
DATASET_DIR="data/eval_v1/eval"
OUTPUT_DIR="data/runs"
TIMEOUT=240

for model in "${MODELS[@]}"; do
  echo "========================================================================"
  echo "[$(date -u +%H:%M:%SZ)] Starting sweep for model=${model}"
  echo "========================================================================"
  uv run ui-bench run \
    --dataset-dir "${DATASET_DIR}" \
    --provider codex \
    --codex-model "${model}" \
    --codex-timeout-seconds "${TIMEOUT}" \
    --output-dir "${OUTPUT_DIR}" \
    || {
      echo "[$(date -u +%H:%M:%SZ)] sweep for ${model} exited non-zero; continuing"
    }
  echo "[$(date -u +%H:%M:%SZ)] Finished sweep for model=${model}"
done

echo "========================================================================"
echo "[$(date -u +%H:%M:%SZ)] All Codex sweeps complete."
echo "========================================================================"

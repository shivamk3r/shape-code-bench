"""Validate a complete frozen evaluation and export public scores and provenance.

Raw model output stays in the local run directory. Only aggregate scores,
per-sample metrics, hashes, and the experimental protocol are exported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from analyze import _build_main_df, _model_label

from shape_code_bench.runner import _load_reusable_result, load_dataset_samples

ROOT = Path(__file__).resolve().parents[1]


def export_run(
    run_dir: Path, output_dir: Path, dataset_dir: Path, dataset_version: str,
    *, bootstrap: int = 1000, seed: int = 2026,
) -> None:
    config = json.loads((run_dir / "run_config.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    samples = load_dataset_samples(str(dataset_dir))
    expected_ids = [sample.sample_id for sample in samples]
    if (
        summary.get("status") != "complete"
        or summary["total_samples"] != len(samples)
        or config["selected_sample_ids"] != expected_ids
        or not config["invocations"]
        or config["invocations"][-1]["status"] != "complete"
    ):
        raise ValueError("Only complete evaluations of the entire dataset can be published.")
    if dataset_version == "eval_v1" and (
        len(samples) != 150
        or any(sum(sample.difficulty == tier for sample in samples) != 50
               for tier in ("easy", "medium", "hard"))
    ):
        raise ValueError("eval_v1 requires 150 samples, with 50 in each difficulty tier.")

    payloads = []
    metrics = []
    artifact_hashes = {}
    for sample in samples:
        path = run_dir / "samples" / f"{sample.sample_id}.json"
        payload = json.loads(path.read_text())
        validated = _load_reusable_result(run_dir / "samples", sample, config["model"])
        if validated is None:
            raise ValueError(f"Unusable prediction or adapter error: {sample.sample_id}")
        if validated.evaluation.to_dict() != payload["evaluation"]:
            raise ValueError(f"Stored scores do not reproduce: {sample.sample_id}")
        if config["input_hashes"][sample.sample_id] != payload["input_hashes"]:
            raise ValueError(f"Run input hash mismatch: {sample.sample_id}")
        payloads.append(payload)
        metrics.append({
            "sample_id": sample.sample_id, "difficulty": sample.difficulty, "seed": sample.seed,
            **payload["input_hashes"], **payload["evaluation"],
            "latency_ms": payload["prediction"]["latency_ms"],
        })
        artifact_hashes[sample.sample_id] = hashlib.sha256(path.read_bytes()).hexdigest()

    run = {
        "model_label": _model_label(summary, config["adapter"]),
        "provider": config["provider"], "model": config["model"], "samples": payloads,
    }
    table = _build_main_df([run], bootstrap=bootstrap, seed=seed)
    aggregate_keys = ("exact_match_rate", "mean_pixel_accuracy", "mean_foreground_iou", "parse_success_rate")
    for _, row in table.iterrows():
        source = summary if row["difficulty"] == "all" else summary["by_difficulty"][row["difficulty"]]
        if any(abs(float(row[key]) - source[key]) > 1e-12 for key in aggregate_keys):
            raise ValueError("Run summary does not match the per-sample scores.")

    protocol = {
        "schema_version": 1,
        "dataset_version": dataset_version,
        "source_run_id": config["run_id"],
        "evaluation_date": config["invocations"][0]["started_at"][:10],
        "provider": config["provider"], "model": config["model"],
        "adapter": {key: value for key, value in config["adapter"].items() if key != "codex_binary"},
        "environment": config["environment"],
        "prompt": config["prompt"],
        "source_hashes": config["source_hashes"],
        "dataset_sha256": hashlib.sha256(json.dumps(
            config["input_hashes"], sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "sample_counts": {"all": len(samples), **{
            tier: sum(sample.difficulty == tier for sample in samples)
            for tier in ("easy", "medium", "hard")
        }},
        "bootstrap": {"resamples": bootstrap, "seed": seed, "confidence_level": 0.95},
        "invocations": [{
            "status": item["status"],
            "started_at": item["started_at"], "finished_at": item.get("finished_at"),
            "workers": item["workers"], "selected_samples": len(item["selected_sample_ids"]),
            "reused_samples": len(item["reused_sample_ids"]),
            "new_samples": len(item["requested_sample_ids"]),
            "wall_time_seconds": item.get("wall_time_seconds"),
        } for item in config["invocations"]],
        "sample_artifact_sha256": artifact_hashes,
    }
    verification_path = run_dir / "execution_verification.json"
    if verification_path.exists():
        observation = json.loads(verification_path.read_text())
        protocol["observed_concurrent_codex_samples"] = observation["observed_concurrent_codex_samples"]
    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "main_results.csv", index=False)
    with (output_dir / "sample_metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(metrics)
    public_summary = {key: value for key, value in summary.items() if key != "dataset_dir"}
    for name, value in (("protocol", protocol), ("summary", public_summary)):
        (output_dir / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "data/eval_v1/eval")
    parser.add_argument("--dataset-version", default="eval_v1")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if args.bootstrap_samples < 1:
        parser.error("--bootstrap-samples must be positive")
    export_run(args.run_dir, args.output_dir, args.dataset_dir, args.dataset_version,
               bootstrap=args.bootstrap_samples, seed=args.seed)
    print(f"Exported validated evaluation to {args.output_dir}")


if __name__ == "__main__":
    main()

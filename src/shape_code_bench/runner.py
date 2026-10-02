from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from shape_code_bench.adapters.base import ModelAdapter, PredictionRequest, PredictionResult
from shape_code_bench.evaluator import evaluate_program
from shape_code_bench.normalization import normalize_prediction_text
from shape_code_bench.prompts import PromptSpec, build_zero_shot_prompt_spec
from shape_code_bench.types import EvaluationResult


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    split: str
    difficulty: str
    seed: int
    image_path: Path
    metadata_path: Path
    ground_truth_program: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BenchmarkSampleResult:
    sample: BenchmarkSample
    prediction: PredictionResult
    evaluation: EvaluationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample.sample_id,
            "split": self.sample.split,
            "difficulty": self.sample.difficulty,
            "seed": self.sample.seed,
            "image_path": str(self.sample.image_path),
            "metadata_path": str(self.sample.metadata_path),
            "input_hashes": _sample_hashes(self.sample),
            "prediction_sha256": _json_hash(self.prediction.to_dict()),
            "prediction": self.prediction.to_dict(),
            "evaluation": self.evaluation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkRunResult:
    run_id: str
    output_dir: Path
    run_config_path: Path
    summary_path: Path
    sample_results: tuple[BenchmarkSampleResult, ...]
    summary: dict[str, Any]


def load_dataset_samples(dataset_dir: str) -> list[BenchmarkSample]:
    root = Path(dataset_dir)
    if not root.exists():
        raise ValueError(f"Dataset directory does not exist: {root}")

    samples: list[BenchmarkSample] = []
    for metadata_path in sorted(root.rglob("*.json")):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        required = {"sample_id", "split", "difficulty", "seed", "ground_truth_program"}
        if not required.issubset(payload):
            continue

        image_path = metadata_path.with_suffix(".png")
        if not image_path.exists():
            continue

        samples.append(
            BenchmarkSample(
                sample_id=str(payload["sample_id"]),
                split=str(payload["split"]),
                difficulty=str(payload["difficulty"]),
                seed=int(payload["seed"]),
                image_path=image_path,
                metadata_path=metadata_path,
                ground_truth_program=str(payload["ground_truth_program"]),
                metadata=payload,
            )
        )

    samples.sort(key=lambda sample: (sample.split, sample.difficulty, sample.sample_id))
    if not samples:
        raise ValueError(f"No generated benchmark samples found under {root}.")
    return samples


def run_benchmark(
    dataset_dir: str,
    adapter: ModelAdapter,
    limit: int | None,
    output_dir: str,
    prompt_spec: PromptSpec | None = None,
    *,
    workers: int = 1,
    resume_from: str | None = None,
    sample_ids: list[str] | None = None,
    progress_callback: Callable[[int, int, str, bool], None] | None = None,
) -> BenchmarkRunResult:
    if workers < 1:
        raise ValueError("workers must be at least 1.")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1 when provided.")
    all_samples = load_dataset_samples(dataset_dir)
    ids = [sample.sample_id for sample in all_samples]
    if len(ids) != len(set(ids)) or any(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", sample_id) is None for sample_id in ids
    ):
        raise ValueError("Dataset sample IDs must be unique and safe filenames.")
    if sample_ids is not None:
        unknown = set(sample_ids) - set(ids)
        if unknown:
            raise ValueError(f"Unknown sample IDs: {sorted(unknown)}")
        all_samples = [sample for sample in all_samples if sample.sample_id in sample_ids]
    selected_samples = all_samples if limit is None else all_samples[:limit]
    if not selected_samples:
        raise ValueError("No samples selected for this run.")

    prompt_spec = prompt_spec or build_zero_shot_prompt_spec()
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    adapter_config = adapter.to_config()
    source_hashes = _protocol_source_hashes(adapter)
    protocol_fingerprint = _json_hash({
        "adapter": adapter_config, "prompt": prompt_spec.to_dict(), "sources": source_hashes,
    })
    environment = {
        "python": platform.python_version(),
        "pillow": version("Pillow"),
        "numpy": version("numpy"),
        "adapter_runtime": adapter.runtime_info() if hasattr(adapter, "runtime_info") else {},
    }
    previous_config = None
    if resume_from is not None:
        run_root = Path(resume_from)
        previous_config = json.loads((run_root / "run_config.json").read_text(encoding="utf-8"))
        if (
            previous_config.get("protocol_fingerprint") != protocol_fingerprint
            or previous_config.get("dataset_dir") != str(Path(dataset_dir).resolve())
            or previous_config.get("environment") != environment
        ):
            raise ValueError("Cannot resume: dataset, prompt, adapter, scoring code, or environment changed.")
        run_id = previous_config["run_id"]
    else:
        run_id = _build_run_id(adapter.provider, adapter.model)
        run_root = Path(output_dir) / run_id
        run_root.mkdir(parents=True, exist_ok=False)
    sample_output_dir = run_root / "samples"
    sample_output_dir.mkdir(parents=True, exist_ok=True)

    invocations = [dict(item) for item in previous_config.get("invocations", [])] if previous_config else []
    if invocations and invocations[-1]["status"] == "running":
        invocations[-1].update({"status": "interrupted", "interrupted_at": started_at})

    run_config = {
        "run_id": run_id,
        "dataset_dir": str(Path(dataset_dir).resolve()),
        "provider": adapter.provider,
        "model": adapter.model,
        "limit": limit,
        "prompt": prompt_spec.to_dict(),
        "adapter": adapter_config,
        "selected_sample_ids": [sample.sample_id for sample in selected_samples],
        "artifact_schema_version": 2,
        "workers": workers,
        "source_hashes": source_hashes,
        "protocol_fingerprint": protocol_fingerprint,
        "environment": environment,
        "input_hashes": {sample.sample_id: _sample_hashes(sample) for sample in selected_samples},
        "invocations": invocations,
    }
    results_by_id: dict[str, BenchmarkSampleResult] = {}
    pending: list[BenchmarkSample] = []
    for sample in selected_samples:
        if previous_config and sample.sample_id in previous_config.get("input_hashes", {}):
            if previous_config["input_hashes"][sample.sample_id] != _sample_hashes(sample):
                raise ValueError(f"Cannot resume: input changed for {sample.sample_id}.")
        cached = _load_reusable_result(sample_output_dir, sample, adapter.model) if previous_config else None
        if cached is None:
            pending.append(sample)
        else:
            results_by_id[sample.sample_id] = cached

    reused_ids = sorted(results_by_id)
    invocation = {
        "started_at": started_at, "status": "running", "limit": limit, "workers": workers,
        "selected_sample_ids": run_config["selected_sample_ids"],
        "reused_sample_ids": reused_ids,
        "requested_sample_ids": [sample.sample_id for sample in pending],
    }
    run_config["invocations"].append(invocation)
    run_config_path = run_root / "run_config.json"
    _write_json(run_config_path, run_config)
    summary_path = run_root / "summary.json"
    # A resumed or interrupted run must never retain an apparently complete summary.
    summary_path.unlink(missing_ok=True)

    def save_result(result: BenchmarkSampleResult, reused: bool) -> None:
        results_by_id[result.sample.sample_id] = result
        _write_json(sample_output_dir / f"{result.sample.sample_id}.json", result.to_dict())
        _write_json(run_root / "progress.json", {
            "run_id": run_id, "status": "running", "total_samples": len(selected_samples),
            "completed_samples": len(results_by_id), "reused_samples": len(reused_ids),
        })
        if progress_callback:
            progress_callback(len(results_by_id), len(selected_samples), result.sample.sample_id, reused)

    for sample_id in reused_ids:
        save_result(results_by_id[sample_id], True)
    if workers == 1:
        for sample in pending:
            save_result(_predict_sample(sample, adapter, prompt_spec), False)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_predict_sample, sample, adapter, prompt_spec) for sample in pending]
            for future in as_completed(futures):
                save_result(future.result(), False)

    # Completion order cannot affect aggregate scores or returned sample order.
    sample_results = [results_by_id[sample.sample_id] for sample in selected_samples]

    summary = _build_summary(run_id, dataset_dir, adapter, prompt_spec, sample_results)
    summary.update({
        "workers": workers, "reused_samples": len(reused_ids), "new_samples": len(pending),
        "wall_time_seconds": time.perf_counter() - started, "status": "complete",
    })
    invocation.update({
        "status": "complete", "finished_at": datetime.now(timezone.utc).isoformat(),
        "wall_time_seconds": summary["wall_time_seconds"],
    })
    _write_json(run_config_path, run_config)
    _write_json(summary_path, summary)
    _write_json(run_root / "progress.json", {
        "run_id": run_id, "status": "complete", "total_samples": len(selected_samples),
        "completed_samples": len(sample_results), "reused_samples": len(reused_ids),
    })

    return BenchmarkRunResult(
        run_id=run_id,
        output_dir=run_root,
        run_config_path=run_config_path,
        summary_path=summary_path,
        sample_results=tuple(sample_results),
        summary=summary,
    )


def _build_run_id(provider: str, model: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_model = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()
    return f"{timestamp}-{provider}-{safe_model}"


def _build_summary(
    run_id: str,
    dataset_dir: str,
    adapter: ModelAdapter,
    prompt_spec: PromptSpec,
    sample_results: list[BenchmarkSampleResult],
) -> dict[str, Any]:
    summary = _summarize_results(sample_results)
    by_difficulty = {
        difficulty: _summarize_results(
            [sample_result for sample_result in sample_results if sample_result.sample.difficulty == difficulty]
        )
        for difficulty in sorted({sample_result.sample.difficulty for sample_result in sample_results})
    }

    return {
        "run_id": run_id,
        "dataset_dir": str(Path(dataset_dir).resolve()),
        "provider": adapter.provider,
        "model": adapter.model,
        "prompt_mode": prompt_spec.mode,
        "total_samples": len(sample_results),
        **summary,
        "by_difficulty": by_difficulty,
    }


def _summarize_results(sample_results: list[BenchmarkSampleResult]) -> dict[str, Any]:
    count = len(sample_results)
    if count == 0:
        return {
            "total_samples": 0,
            "exact_match_rate": 0.0,
            "mean_pixel_accuracy": 0.0,
            "mean_foreground_iou": 0.0,
            "parse_success_rate": 0.0,
            "execution_success_rate": 0.0,
            "error_type_counts": {},
            "adapter_error_type_counts": {},
        }

    exact_match_rate = sum(result.evaluation.exact_match for result in sample_results) / count
    mean_pixel_accuracy = sum(result.evaluation.pixel_accuracy for result in sample_results) / count
    mean_foreground_iou = sum(result.evaluation.foreground_iou for result in sample_results) / count
    parse_success_rate = sum(result.evaluation.parse_success for result in sample_results) / count
    execution_success_rate = sum(result.evaluation.execution_success for result in sample_results) / count

    evaluation_error_counts = Counter(
        result.evaluation.error_type or "none" for result in sample_results
    )
    adapter_error_counts = Counter(result.prediction.error_type or "none" for result in sample_results)

    return {
        "total_samples": count,
        "exact_match_rate": exact_match_rate,
        "mean_pixel_accuracy": mean_pixel_accuracy,
        "mean_foreground_iou": mean_foreground_iou,
        "parse_success_rate": parse_success_rate,
        "execution_success_rate": execution_success_rate,
        "error_type_counts": dict(sorted(evaluation_error_counts.items())),
        "adapter_error_type_counts": dict(sorted(adapter_error_counts.items())),
        "mean_latency_ms": sum(result.prediction.latency_ms for result in sample_results) / count,
    }


def _predict_sample(
    sample: BenchmarkSample, adapter: ModelAdapter, prompt: PromptSpec,
) -> BenchmarkSampleResult:
    request = PredictionRequest(
        sample_id=sample.sample_id, image_path=sample.image_path,
        system_instruction=prompt.system_instruction, prompt_text=prompt.user_text,
    )
    try:
        prediction = adapter.predict(request)
    except Exception as exc:
        prediction = PredictionResult.from_error(
            model=adapter.model, error_type="adapter_exception", error_message=str(exc),
        )
    evaluation = evaluate_program(str(sample.image_path), prediction.normalized_text)
    return BenchmarkSampleResult(sample=sample, prediction=prediction, evaluation=evaluation)


def _load_reusable_result(
    directory: Path, sample: BenchmarkSample, model: str,
) -> BenchmarkSampleResult | None:
    try:
        payload = json.loads((directory / f"{sample.sample_id}.json").read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        if any(payload.get(key) != getattr(sample, key) for key in ("sample_id", "split", "difficulty", "seed")):
            return None
        if payload.get("input_hashes") != _sample_hashes(sample):
            return None
        if payload.get("prediction_sha256") != _json_hash(payload["prediction"]):
            return None
        prediction = PredictionResult(**payload["prediction"])
        if (
            prediction.model != model or prediction.error_type is not None
            or not isinstance(prediction.raw_text, str)
            or prediction.normalized_text != normalize_prediction_text(prediction.raw_text)
            or not isinstance(prediction.latency_ms, int) or prediction.latency_ms < 0
        ):
            return None
    except (OSError, ValueError, TypeError, KeyError):
        return None
    # Model syntax failures remain scored failures; do not resample for a better score.
    evaluation = evaluate_program(str(sample.image_path), prediction.normalized_text)
    return BenchmarkSampleResult(sample=sample, prediction=prediction, evaluation=evaluation)


def _sample_hashes(sample: BenchmarkSample) -> dict[str, str]:
    return {"image_sha256": _file_hash(sample.image_path), "metadata_sha256": _file_hash(sample.metadata_path)}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _protocol_source_hashes(adapter: ModelAdapter) -> dict[str, str]:
    root = Path(__file__).parent
    hashes = {name: _file_hash(root / name) for name in (
        "dsl.py", "renderer.py", "evaluator.py", "types.py", "normalization.py", "prompts.py",
    )}
    module = sys.modules[type(adapter).__module__]
    if getattr(module, "__file__", None):
        hashes["adapter"] = _file_hash(Path(module.__file__))
    return hashes


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shape_code_bench.adapters.base import ModelAdapter, PredictionRequest, PredictionResult
from shape_code_bench.evaluator import evaluate_program
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
) -> BenchmarkRunResult:
    all_samples = load_dataset_samples(dataset_dir)
    selected_samples = all_samples if limit is None else all_samples[:limit]
    if not selected_samples:
        raise ValueError("No samples selected for this run.")

    prompt_spec = prompt_spec or build_zero_shot_prompt_spec()
    run_id = _build_run_id(adapter.provider, adapter.model)
    run_root = Path(output_dir) / run_id
    sample_output_dir = run_root / "samples"
    sample_output_dir.mkdir(parents=True, exist_ok=True)

    run_config = {
        "run_id": run_id,
        "dataset_dir": str(Path(dataset_dir).resolve()),
        "provider": adapter.provider,
        "model": adapter.model,
        "limit": limit,
        "prompt": prompt_spec.to_dict(),
        "adapter": adapter.to_config(),
        "selected_sample_ids": [sample.sample_id for sample in selected_samples],
    }
    run_config_path = run_root / "run_config.json"
    run_config_path.write_text(json.dumps(run_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sample_results: list[BenchmarkSampleResult] = []
    for sample in selected_samples:
        request = PredictionRequest(
            sample_id=sample.sample_id,
            image_path=sample.image_path,
            system_instruction=prompt_spec.system_instruction,
            prompt_text=prompt_spec.user_text,
        )

        try:
            prediction = adapter.predict(request)
        except Exception as exc:
            prediction = PredictionResult.from_error(
                model=getattr(adapter, "model", "unknown"),
                error_type="adapter_exception",
                error_message=str(exc),
            )

        evaluation = evaluate_program(str(sample.image_path), prediction.normalized_text)
        sample_result = BenchmarkSampleResult(sample=sample, prediction=prediction, evaluation=evaluation)
        sample_results.append(sample_result)

        sample_result_path = sample_output_dir / f"{sample.sample_id}.json"
        sample_result_path.write_text(
            json.dumps(sample_result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary = _build_summary(run_id, dataset_dir, adapter, prompt_spec, sample_results)
    summary_path = run_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return BenchmarkRunResult(
        run_id=run_id,
        output_dir=run_root,
        run_config_path=run_config_path,
        summary_path=summary_path,
        sample_results=tuple(sample_results),
        summary=summary,
    )


def _build_run_id(provider: str, model: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
        "exact_match_rate": exact_match_rate,
        "mean_pixel_accuracy": mean_pixel_accuracy,
        "mean_foreground_iou": mean_foreground_iou,
        "parse_success_rate": parse_success_rate,
        "execution_success_rate": execution_success_rate,
        "error_type_counts": dict(sorted(evaluation_error_counts.items())),
        "adapter_error_type_counts": dict(sorted(adapter_error_counts.items())),
    }

from __future__ import annotations

import json
from pathlib import Path

from shape_code_bench.adapters import PredictionRequest, PredictionResult
from shape_code_bench.generator import write_generated_sample
from shape_code_bench.runner import run_benchmark


class FakeAdapter:
    provider = "fake"
    model = "fake-model"

    def __init__(self, predictions: dict[str, PredictionResult]) -> None:
        self.predictions = predictions
        self.requests: list[PredictionRequest] = []

    def predict(self, request: PredictionRequest) -> PredictionResult:
        self.requests.append(request)
        return self.predictions[request.sample_id]

    def to_config(self) -> dict[str, object]:
        return {"provider": self.provider, "model": self.model}


def test_run_benchmark_writes_artifacts_and_summary(tmp_path: Path) -> None:
    dataset_dir, metadata_by_sample = _build_dataset(tmp_path, [("easy", 5), ("medium", 9)])
    adapter = FakeAdapter(
        {
            sample_id: PredictionResult(
                raw_text=metadata["ground_truth_program"],
                normalized_text=metadata["ground_truth_program"],
                model="fake-model",
                request_id="req_1",
                usage={"total_tokens": 10},
                latency_ms=12,
                error_type=None,
            )
            for sample_id, metadata in metadata_by_sample.items()
        }
    )

    result = run_benchmark(
        dataset_dir=str(dataset_dir),
        adapter=adapter,
        limit=None,
        output_dir=str(tmp_path / "runs"),
    )

    assert result.summary["total_samples"] == 2
    assert result.summary["exact_match_rate"] == 1.0
    assert result.summary["parse_success_rate"] == 1.0
    assert result.run_config_path.exists()
    assert result.summary_path.exists()
    assert len(list((result.output_dir / "samples").glob("*.json"))) == 2

    summary_payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary_payload["by_difficulty"]["easy"]["exact_match_rate"] == 1.0
    assert summary_payload["by_difficulty"]["medium"]["exact_match_rate"] == 1.0


def test_run_benchmark_aggregates_parse_failures(tmp_path: Path) -> None:
    dataset_dir, metadata_by_sample = _build_dataset(tmp_path, [("easy", 5), ("medium", 9)])
    sample_ids = sorted(metadata_by_sample)
    valid_id = sample_ids[0]
    invalid_id = sample_ids[1]

    adapter = FakeAdapter(
        {
            valid_id: PredictionResult(
                raw_text=metadata_by_sample[valid_id]["ground_truth_program"],
                normalized_text=metadata_by_sample[valid_id]["ground_truth_program"],
                model="fake-model",
                request_id="req_1",
                usage={"total_tokens": 10},
                latency_ms=12,
                error_type=None,
            ),
            invalid_id: PredictionResult(
                raw_text="triangle(cx=1, cy=2, size=3)",
                normalized_text="triangle(cx=1, cy=2, size=3)",
                model="fake-model",
                request_id="req_2",
                usage={"total_tokens": 10},
                latency_ms=8,
                error_type=None,
            ),
        }
    )

    result = run_benchmark(
        dataset_dir=str(dataset_dir),
        adapter=adapter,
        limit=None,
        output_dir=str(tmp_path / "runs"),
    )

    assert result.summary["parse_success_rate"] == 0.5
    assert result.summary["execution_success_rate"] == 0.5
    assert result.summary["error_type_counts"]["unsupported_function"] == 1


def test_run_benchmark_respects_limit(tmp_path: Path) -> None:
    dataset_dir, metadata_by_sample = _build_dataset(tmp_path, [("easy", 5), ("medium", 9), ("hard", 12)])
    adapter = FakeAdapter(
        {
            sample_id: PredictionResult(
                raw_text=metadata["ground_truth_program"],
                normalized_text=metadata["ground_truth_program"],
                model="fake-model",
                request_id=f"req_{index}",
                usage={"total_tokens": 10},
                latency_ms=10,
                error_type=None,
            )
            for index, (sample_id, metadata) in enumerate(metadata_by_sample.items(), start=1)
        }
    )

    result = run_benchmark(
        dataset_dir=str(dataset_dir),
        adapter=adapter,
        limit=2,
        output_dir=str(tmp_path / "runs"),
    )

    assert result.summary["total_samples"] == 2
    assert len(result.sample_results) == 2


def _build_dataset(
    tmp_path: Path,
    specs: list[tuple[str, int]],
) -> tuple[Path, dict[str, dict[str, object]]]:
    output_root = tmp_path / "generated"
    metadata_by_sample: dict[str, dict[str, object]] = {}
    for difficulty, seed in specs:
        generated = write_generated_sample(split="train", difficulty=difficulty, seed=seed, output_dir=str(output_root))
        metadata_path = Path(generated["metadata_path"])
        metadata_by_sample[generated["sample_id"]] = json.loads(metadata_path.read_text(encoding="utf-8"))
    return output_root / "train", metadata_by_sample


from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from shape_code_bench.adapters import PredictionRequest, PredictionResult
from shape_code_bench.generator import write_generated_sample
from shape_code_bench.runner import load_dataset_samples, run_benchmark


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


def _perfect_adapter(metadata_by_sample) -> FakeAdapter:
    return FakeAdapter({
        sample_id: PredictionResult(
            raw_text=metadata["ground_truth_program"],
            normalized_text=metadata["ground_truth_program"], model="fake-model",
            request_id=sample_id, usage=None, latency_ms=1, error_type=None,
        )
        for sample_id, metadata in metadata_by_sample.items()
    })


def test_parallel_run_is_bounded_and_preserves_dataset_order(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", seed) for seed in range(9)])
    barrier = threading.Barrier(3, timeout=5)
    lock = threading.Lock()

    class ParallelAdapter(FakeAdapter):
        active = 0
        maximum = 0

        def predict(self, request):
            with lock:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            barrier.wait()
            result = super().predict(request)
            with lock:
                self.active -= 1
            return result

    adapter = ParallelAdapter(_perfect_adapter(metadata).predictions)
    result = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"), workers=3)
    assert adapter.maximum == 3
    assert result.summary["exact_match_rate"] == 1
    assert result.summary["workers"] == 3
    assert [item.sample.sample_id for item in result.sample_results] == [
        sample.sample_id for sample in load_dataset_samples(str(dataset))
    ]


def test_parallel_run_persists_finished_sample_before_slow_one(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("easy", 1)])
    slow_id, fast_id = sorted(metadata)
    release = threading.Event()

    class SlowAdapter(FakeAdapter):
        def predict(self, request):
            if request.sample_id == slow_id:
                assert release.wait(timeout=5)
            return super().predict(request)

    def progress(completed, total, sample_id, reused):
        if completed == 1:
            assert sample_id == fast_id
            assert len(list((tmp_path / "runs").glob("*/samples/*.json"))) == 1
            release.set()

    result = run_benchmark(str(dataset), SlowAdapter(_perfect_adapter(metadata).predictions),
                           None, str(tmp_path / "runs"), workers=2, progress_callback=progress)
    assert result.summary["exact_match_rate"] == 1


def test_resume_extends_pilot_and_reuses_predictions(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("easy", 1), ("medium", 0)])
    adapter = _perfect_adapter(metadata)
    pilot = run_benchmark(str(dataset), adapter, 2, str(tmp_path / "runs"))
    adapter.requests.clear()
    full = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"), workers=8,
                         resume_from=str(pilot.output_dir))
    assert full.output_dir == pilot.output_dir
    assert len(adapter.requests) == 1
    assert full.summary["total_samples"] == 3
    assert full.summary["reused_samples"] == 2
    assert full.summary["new_samples"] == 1
    config = json.loads(full.run_config_path.read_text())
    assert len(config["invocations"]) == 2
    assert len(config["invocations"][-1]["reused_sample_ids"]) == 2
    adapter.requests.clear()
    repeated = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"), workers=2,
                             resume_from=str(full.output_dir))
    assert not adapter.requests
    assert repeated.summary["reused_samples"] == 3
    assert repeated.summary["by_difficulty"]["easy"]["total_samples"] == 2


def test_resume_keeps_model_parse_failures_and_retries_transport_failures(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("medium", 0)])
    invalid_id, failed_id = sorted(metadata)
    adapter = _perfect_adapter(metadata)
    adapter.predictions[invalid_id] = PredictionResult(
        raw_text="triangle()", normalized_text="triangle()", model=adapter.model,
        request_id="invalid", usage=None, latency_ms=1, error_type=None,
    )
    adapter.predictions[failed_id] = PredictionResult.from_error(
        model=adapter.model, error_type="timeout", error_message="timeout",
    )
    pilot = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"))
    adapter.predictions[failed_id] = _perfect_adapter(metadata).predictions[failed_id]
    adapter.requests.clear()
    result = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"),
                           resume_from=str(pilot.output_dir))
    assert [request.sample_id for request in adapter.requests] == [failed_id]
    assert result.summary["parse_success_rate"] == 0.5
    assert result.summary["reused_samples"] == 1


def test_resume_rejects_changed_protocol_and_inputs(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0)])
    adapter = _perfect_adapter(metadata)
    pilot = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"))
    adapter.model = "different-model"
    with pytest.raises(ValueError, match="Cannot resume"):
        run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"),
                       resume_from=str(pilot.output_dir))
    adapter.model = "fake-model"
    sample = load_dataset_samples(str(dataset))[0]
    sample.metadata_path.write_text(sample.metadata_path.read_text() + "\n")
    with pytest.raises(ValueError, match="input changed"):
        run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"),
                       resume_from=str(pilot.output_dir))
    assert len(adapter.requests) == 1


def test_resume_reruns_corrupt_artifact_and_recomputes_cached_scores(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("medium", 0)])
    adapter = _perfect_adapter(metadata)
    pilot = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"))
    first, second = sorted((pilot.output_dir / "samples").glob("*.json"))
    payload = json.loads(first.read_text())
    payload["evaluation"]["foreground_iou"] = 0
    first.write_text(json.dumps(payload))
    second.write_text("{unfinished")
    adapter.requests.clear()
    result = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"),
                           resume_from=str(pilot.output_dir))
    assert len(adapter.requests) == 1
    assert result.summary["exact_match_rate"] == 1
    assert result.summary["mean_foreground_iou"] == 1
    assert json.loads(first.read_text())["evaluation"]["foreground_iou"] == 1


def test_resume_recovers_interrupted_run_with_non_object_artifact(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("medium", 0)])
    adapter = _perfect_adapter(metadata)
    pilot = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"))
    config = json.loads(pilot.run_config_path.read_text())
    config["invocations"][-1]["status"] = "running"
    config["invocations"][-1].pop("finished_at")
    config["invocations"][-1].pop("wall_time_seconds")
    pilot.run_config_path.write_text(json.dumps(config))
    next((pilot.output_dir / "samples").glob("*.json")).write_text("[]")
    adapter.requests.clear()
    resumed = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"),
                            resume_from=str(pilot.output_dir))
    assert len(adapter.requests) == 1
    invocations = json.loads(resumed.run_config_path.read_text())["invocations"]
    assert invocations[0]["status"] == "interrupted"
    assert invocations[1]["status"] == "complete"


def test_runner_validates_selection_and_workers(tmp_path: Path) -> None:
    dataset, metadata = _build_dataset(tmp_path, [("easy", 0), ("medium", 0)])
    adapter = _perfect_adapter(metadata)
    for kwargs in ({"workers": 0}, {"sample_ids": ["unknown"]}):
        with pytest.raises(ValueError):
            run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"), **kwargs)
    selected = next(iter(metadata))
    result = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"), sample_ids=[selected])
    assert len(result.sample_results) == 1
    assert adapter.requests[0].sample_id == selected


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

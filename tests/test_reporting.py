from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from shape_code_bench.generator import write_generated_sample
from shape_code_bench.runner import run_benchmark
from test_runner import _perfect_adapter

ROOT = Path(__file__).resolve().parents[1]


def _report(run_dir: Path, dataset: Path, output: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([
        sys.executable, str(ROOT / "scripts/report_run.py"), "--run-dir", str(run_dir),
        "--dataset-dir", str(dataset), "--dataset-version", "test", "--output-dir", str(output),
    ], env=env, capture_output=True, text=True, timeout=30, check=False)


def _dataset(tmp_path: Path):
    metadata = {}
    for tier in ("easy", "medium", "hard"):
        entry = write_generated_sample(split="test", difficulty=tier, seed=0,
                                       output_dir=str(tmp_path / "dataset"))
        metadata[entry["sample_id"]] = json.loads(Path(entry["metadata_path"]).read_text())
    return tmp_path / "dataset/test", metadata


def test_public_export_is_reproducible_and_contains_only_scores_and_protocol(tmp_path: Path) -> None:
    dataset, metadata = _dataset(tmp_path)
    run = run_benchmark(str(dataset), _perfect_adapter(metadata), None, str(tmp_path / "runs"))
    config = json.loads(run.run_config_path.read_text())
    earlier = {key: value for key, value in config["invocations"][0].items()
               if key not in {"finished_at", "wall_time_seconds"}}
    earlier["status"] = "interrupted"
    config["invocations"].insert(0, earlier)
    run.run_config_path.write_text(json.dumps(config))
    first, second = tmp_path / "first", tmp_path / "second"
    for output in (first, second):
        result = _report(run.output_dir, dataset, output)
        assert result.returncode == 0, result.stderr
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
        text = path.read_text()
        assert "ground_truth_program" not in text
        assert "raw_text" not in text
        assert str(tmp_path) not in text
    with (first / "main_results.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert [row["n"] for row in rows] == ["3", "1", "1", "1"]
    assert all(float(row["mean_foreground_iou"]) == 1 for row in rows)
    protocol = json.loads((first / "protocol.json").read_text())
    assert protocol["sample_counts"] == {"all": 3, "easy": 1, "medium": 1, "hard": 1}
    assert len(protocol["sample_artifact_sha256"]) == 3


def test_public_export_rejects_partial_run_and_unreproducible_scores(tmp_path: Path) -> None:
    dataset, metadata = _dataset(tmp_path)
    adapter = _perfect_adapter(metadata)
    partial = run_benchmark(str(dataset), adapter, 1, str(tmp_path / "runs"))
    result = _report(partial.output_dir, dataset, tmp_path / "partial-report")
    assert result.returncode != 0
    assert "complete evaluations" in result.stderr
    assert not (tmp_path / "partial-report").exists()
    full = run_benchmark(str(dataset), adapter, None, str(tmp_path / "runs"))
    sample_path = next((full.output_dir / "samples").glob("*.json"))
    payload = json.loads(sample_path.read_text())
    payload["evaluation"]["pixel_accuracy"] = 0
    sample_path.write_text(json.dumps(payload))
    result = _report(full.output_dir, dataset, tmp_path / "corrupt-report")
    assert result.returncode != 0
    assert "Stored scores do not reproduce" in result.stderr
    assert not (tmp_path / "corrupt-report").exists()

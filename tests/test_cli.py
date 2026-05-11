from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from shape_code_bench.adapters import PredictionRequest, PredictionResult
from shape_code_bench.cli import main
from shape_code_bench.generator import write_generated_sample


ROOT = Path(__file__).resolve().parents[1]


def test_cli_generate_render_and_eval_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    generate = _run_cli(
        [
            "generate",
            "--split",
            "train",
            "--difficulty",
            "easy",
            "--count",
            "1",
            "--seed",
            "21",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert generate.returncode == 0, generate.stderr

    generated_payload = json.loads(generate.stdout)
    generated_entry = generated_payload["generated"][0]
    metadata_path = Path(generated_entry["metadata_path"])
    image_path = Path(generated_entry["image_path"])

    assert metadata_path.exists()
    assert image_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    prediction_path = tmp_path / "prediction.dsl"
    prediction_path.write_text(metadata["ground_truth_program"], encoding="utf-8")

    rendered_path = tmp_path / "rendered.png"
    render = _run_cli(
        [
            "render",
            "--program-file",
            str(prediction_path),
            "--output-file",
            str(rendered_path),
        ]
    )
    assert render.returncode == 0, render.stderr
    assert rendered_path.exists()

    eval_output_path = tmp_path / "eval.json"
    evaluation = _run_cli(
        [
            "eval",
            "--target-image",
            str(image_path),
            "--prediction-file",
            str(prediction_path),
            "--output-file",
            str(eval_output_path),
        ]
    )
    assert evaluation.returncode == 0, evaluation.stderr

    eval_payload = json.loads(evaluation.stdout)
    assert eval_payload["exact_match"] is True
    assert eval_output_path.exists()


def test_cli_run_writes_summary_with_fake_adapter(tmp_path: Path, monkeypatch, capsys) -> None:
    output_root = tmp_path / "generated"
    generated = write_generated_sample(split="train", difficulty="easy", seed=21, output_dir=str(output_root))
    metadata = json.loads(Path(generated["metadata_path"]).read_text(encoding="utf-8"))
    dataset_dir = output_root / "train"

    class FakeAdapter:
        provider = "fake"
        model = "fake-model"

        def predict(self, request: PredictionRequest) -> PredictionResult:
            return PredictionResult(
                raw_text=metadata["ground_truth_program"],
                normalized_text=metadata["ground_truth_program"],
                model=self.model,
                request_id="req_123",
                usage={"total_tokens": 10},
                latency_ms=5,
                error_type=None,
            )

        def to_config(self) -> dict[str, object]:
            return {"provider": self.provider, "model": self.model}

    monkeypatch.setattr("shape_code_bench.cli._build_adapter_from_args", lambda args: FakeAdapter())

    exit_code = main(
        [
            "run",
            "--dataset-dir",
            str(dataset_dir),
            "--provider",
            "openai",
            "--limit",
            "1",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["total_samples"] == 1
    assert Path(payload["summary_path"]).exists()
    assert Path(payload["run_config_path"]).exists()


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}:{existing_pythonpath}"
    return subprocess.run(
        [sys.executable, "-m", "shape_code_bench.cli", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

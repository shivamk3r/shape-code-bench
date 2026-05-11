from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from shape_code_bench.cli import main
from shape_code_bench.generator import write_smoke_test_dataset


@pytest.mark.skipif(
    os.getenv("SHAPE_CODE_BENCH_RUN_LIVE_OPENAI") != "1",
    reason="Live OpenAI smoke test is opt-in. Set SHAPE_CODE_BENCH_RUN_LIVE_OPENAI=1 to enable it.",
)
def test_live_openai_smoke_run(tmp_path: Path) -> None:
    load_dotenv(override=False)
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set.")

    dataset_root = tmp_path / "generated"
    write_smoke_test_dataset(str(dataset_root))
    dataset_dir = dataset_root / "smoke"
    runs_root = tmp_path / "runs"

    exit_code = main(
        [
            "run",
            "--dataset-dir",
            str(dataset_dir),
            "--provider",
            "openai",
            "--model",
            "gpt-5.5",
            "--reasoning-effort",
            "low",
            "--image-detail",
            "low",
            "--max-output-tokens",
            "256",
            "--limit",
            "2",
            "--output-dir",
            str(runs_root),
        ]
    )

    assert exit_code == 0

    run_dirs = sorted(path for path in runs_root.iterdir() if path.is_dir())
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    sample_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "samples").glob("*.json"))
    ]

    assert summary["total_samples"] == 2
    assert len(sample_payloads) == 2
    assert any(payload["prediction"]["raw_text"].strip() for payload in sample_payloads)

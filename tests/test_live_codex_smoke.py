from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from shape_code_bench.cli import main
from shape_code_bench.generator import write_smoke_test_dataset


@pytest.mark.skipif(
    os.getenv("SHAPE_CODE_BENCH_RUN_LIVE_CODEX") != "1",
    reason="Live Codex smoke test is opt-in. Set SHAPE_CODE_BENCH_RUN_LIVE_CODEX=1 to enable it.",
)
def test_live_codex_smoke_run(tmp_path: Path) -> None:
    if shutil.which("codex") is None:
        pytest.skip("codex CLI not found on PATH.")

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
            "codex",
            "--codex-model",
            os.getenv("SHAPE_CODE_BENCH_CODEX_SMOKE_MODEL", "gpt-5.5"),
            "--codex-timeout-seconds",
            "240",
            "--codex-max-retries",
            "0",
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
    # At least one sample should produce non-empty text through Codex.
    assert any(payload["prediction"]["raw_text"].strip() for payload in sample_payloads)

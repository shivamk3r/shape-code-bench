"""Freeze the ShapeCodeBench eval_v1 dataset.

Generates 50 samples per difficulty tier (seeds 0..49), writes them under
``data/eval_v1/<difficulty>/`` alongside a manifest and SHA256SUMS file.
Re-running this script is idempotent given the same ShapeCodeBench version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from shape_code_bench.generator import write_generated_sample

EVAL_SPLIT = "eval"
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")
DEFAULT_SAMPLES_PER_TIER = 50


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the eval_v1 dataset.")
    parser.add_argument("--output-root", default="data/eval_v1", help="Where to write the frozen dataset.")
    parser.add_argument(
        "--samples-per-tier",
        type=int,
        default=DEFAULT_SAMPLES_PER_TIER,
        help="Number of samples to generate for each difficulty tier.",
    )
    parser.add_argument(
        "--start-seed",
        type=int,
        default=0,
        help="First seed to use per tier. Seeds are contiguous from this value.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_splits: list[dict[str, object]] = []
    image_paths: list[Path] = []

    for difficulty in DIFFICULTIES:
        seeds = list(range(args.start_seed, args.start_seed + args.samples_per_tier))
        for seed in seeds:
            result = write_generated_sample(
                split=EVAL_SPLIT,
                difficulty=difficulty,
                seed=seed,
                output_dir=str(output_root),
            )
            image_paths.append(Path(result["image_path"]))

        manifest_splits.append(
            {
                "split": EVAL_SPLIT,
                "difficulty": difficulty,
                "seeds": seeds,
                "count": len(seeds),
            }
        )

    generator_commit = _git_revision()
    manifest = {
        "dataset_id": "shape-code-bench-eval-v1",
        "shape_code_bench_version": "0.1.0",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator_commit": generator_commit,
        "splits": manifest_splits,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sha_path = output_root / "SHA256SUMS"
    sha_lines: list[str] = []
    for image_path in sorted(image_paths):
        digest = _sha256(image_path)
        relative = image_path.relative_to(output_root)
        sha_lines.append(f"{digest}  {relative}")
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "manifest_path": str(manifest_path),
                "sha256sums_path": str(sha_path),
                "total_samples": len(image_paths),
            },
            indent=2,
        )
    )
    return 0


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    revision = completed.stdout.strip()
    return revision or None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

"""Empirically validate render-order invariance of the V1 renderer.

Generates 100 random scenes (≈33/33/34 across easy/medium/hard), then for each
scene shuffles the shape tuple 10 deterministic ways and re-renders. Compares
every shuffle's pixel array against the canonical-order render with
``np.array_equal``. Any mismatch is recorded with the offending DSL programs
and PNGs for inspection.

Writes a JSON summary to ``data/runs/determinism/<UTC-timestamp>.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ui_bench.dsl import serialize_scene
from ui_bench.generator import generate_scene
from ui_bench.renderer import render_scene
from ui_bench.types import Scene


DIFFICULTIES = ("easy", "medium", "hard")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate render-order invariance.")
    parser.add_argument("--n-programs", type=int, default=100)
    parser.add_argument("--shuffles-per-program", type=int, default=10)
    parser.add_argument("--output-dir", default="data/runs/determinism")
    args = parser.parse_args()

    if args.n_programs < 1:
        raise SystemExit("--n-programs must be at least 1")
    if args.shuffles_per_program < 1:
        raise SystemExit("--shuffles-per-program must be at least 1")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    mismatches_dir = output_root / timestamp / "mismatches"

    started = time.perf_counter()
    by_difficulty: dict[str, dict[str, int]] = {
        d: {"n_programs": 0, "n_shuffles": 0, "n_matches": 0, "n_mismatches": 0}
        for d in DIFFICULTIES
    }
    mismatch_records: list[dict[str, object]] = []
    target_hash_counts: Counter[str] = Counter()

    for i in range(args.n_programs):
        difficulty = DIFFICULTIES[i % 3]
        scene = generate_scene(difficulty, seed=i)
        target_array = _render_array(scene)
        target_hash = _array_hash(target_array)
        target_hash_counts[target_hash] += 1
        by_difficulty[difficulty]["n_programs"] += 1

        rng = np.random.default_rng(seed=10_000 + i)
        for j in range(args.shuffles_per_program):
            shuffled = _shuffle_scene(scene, rng)
            candidate = _render_array(shuffled)
            match = bool(np.array_equal(target_array, candidate))

            by_difficulty[difficulty]["n_shuffles"] += 1
            if match:
                by_difficulty[difficulty]["n_matches"] += 1
            else:
                by_difficulty[difficulty]["n_mismatches"] += 1
                _persist_mismatch(
                    mismatches_dir=mismatches_dir,
                    program_idx=i,
                    shuffle_idx=j,
                    difficulty=difficulty,
                    canonical_scene=scene,
                    shuffled_scene=shuffled,
                    canonical_array=target_array,
                    candidate_array=candidate,
                )
                mismatch_records.append(
                    {
                        "program_idx": i,
                        "shuffle_idx": j,
                        "difficulty": difficulty,
                        "seed": i,
                        "target_hash": target_hash,
                        "shuffled_hash": _array_hash(candidate),
                    }
                )

    elapsed = time.perf_counter() - started
    total_shuffles = args.n_programs * args.shuffles_per_program
    total_matches = sum(d["n_matches"] for d in by_difficulty.values())
    total_mismatches = sum(d["n_mismatches"] for d in by_difficulty.values())

    report = {
        "timestamp": timestamp,
        "n_programs": args.n_programs,
        "shuffles_per_program": args.shuffles_per_program,
        "total_renders": args.n_programs + total_shuffles,
        "total_comparisons": total_shuffles,
        "exact_matches": total_matches,
        "mismatches": total_mismatches,
        "mismatch_rate": total_mismatches / total_shuffles if total_shuffles else 0.0,
        "elapsed_seconds": round(elapsed, 3),
        "by_difficulty": by_difficulty,
        "first_mismatch": mismatch_records[0] if mismatch_records else None,
        "n_unique_target_hashes": len(target_hash_counts),
    }

    report_path = output_root / f"{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


def _shuffle_scene(scene: Scene, rng: np.random.Generator) -> Scene:
    shapes = list(scene.shapes)
    rng.shuffle(shapes)
    return Scene(tuple(shapes))


def _render_array(scene: Scene) -> np.ndarray:
    image = render_scene(scene).convert("L")
    return np.asarray(image, dtype=np.uint8)


def _array_hash(array: np.ndarray) -> str:
    return hashlib.sha256(array.tobytes()).hexdigest()


def _persist_mismatch(
    *,
    mismatches_dir: Path,
    program_idx: int,
    shuffle_idx: int,
    difficulty: str,
    canonical_scene: Scene,
    shuffled_scene: Scene,
    canonical_array: np.ndarray,
    candidate_array: np.ndarray,
) -> None:
    case_dir = mismatches_dir / f"{difficulty}-prog{program_idx:03d}-shuf{shuffle_idx:02d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canonical_array, mode="L").save(case_dir / "canonical.png")
    Image.fromarray(candidate_array, mode="L").save(case_dir / "shuffled.png")
    (case_dir / "canonical.dsl").write_text(serialize_scene(canonical_scene) + "\n", encoding="utf-8")
    (case_dir / "shuffled.dsl").write_text(serialize_scene(shuffled_scene) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

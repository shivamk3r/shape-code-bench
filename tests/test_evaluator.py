from __future__ import annotations

import re
from pathlib import Path

from shape_code_bench.dsl import serialize_scene
from shape_code_bench.evaluator import evaluate_program
from shape_code_bench.generator import generate_scene
from shape_code_bench.renderer import render_scene


def test_evaluate_program_scores_ground_truth_as_perfect(tmp_path: Path) -> None:
    scene = generate_scene("easy", seed=5)
    target_path = tmp_path / "target.png"
    render_scene(scene).save(target_path)

    result = evaluate_program(str(target_path), serialize_scene(scene))

    assert result.exact_match is True
    assert result.pixel_accuracy == 1.0
    assert result.foreground_iou == 1.0
    assert result.parse_success is True
    assert result.execution_success is True
    assert result.error_type is None


def test_evaluate_program_returns_partial_score_for_changed_program(tmp_path: Path) -> None:
    scene = generate_scene("easy", seed=9)
    target_path = tmp_path / "target.png"
    render_scene(scene).save(target_path)

    altered_program = re.sub(
        r"cx=(\d+)",
        lambda match: f"cx={min(511, int(match.group(1)) + 1)}",
        serialize_scene(scene),
        count=1,
    )
    result = evaluate_program(str(target_path), altered_program)

    assert result.exact_match is False
    assert 0.0 <= result.pixel_accuracy < 1.0
    assert 0.0 <= result.foreground_iou < 1.0
    assert result.parse_success is True
    assert result.execution_success is True
    assert result.error_type is None


def test_evaluate_program_gracefully_handles_invalid_predictions(tmp_path: Path) -> None:
    scene = generate_scene("easy", seed=11)
    target_path = tmp_path / "target.png"
    render_scene(scene).save(target_path)

    result = evaluate_program(str(target_path), "triangle(cx=1, cy=2, size=3)")

    assert result.exact_match is False
    assert result.pixel_accuracy == 0.0
    assert result.foreground_iou == 0.0
    assert result.parse_success is False
    assert result.execution_success is False
    assert result.error_type == "unsupported_function"

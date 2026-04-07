from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ui_bench.dsl import DSLValidationError, parse_program
from ui_bench.renderer import render_scene
from ui_bench.types import CANVAS_SIZE, EvaluationResult, FOREGROUND_COLOR


def evaluate_program(target_image_path: str, prediction_text: str) -> EvaluationResult:
    target_image = _load_target_image(Path(target_image_path))

    try:
        scene = parse_program(prediction_text)
    except DSLValidationError as exc:
        return EvaluationResult(
            exact_match=False,
            pixel_accuracy=0.0,
            foreground_iou=0.0,
            parse_success=False,
            execution_success=False,
            error_type=exc.error_type,
        )

    try:
        predicted_image = render_scene(scene)
    except Exception:
        return EvaluationResult(
            exact_match=False,
            pixel_accuracy=0.0,
            foreground_iou=0.0,
            parse_success=True,
            execution_success=False,
            error_type="render_error",
        )

    target_array = np.asarray(target_image, dtype=np.uint8)
    predicted_array = np.asarray(predicted_image, dtype=np.uint8)

    exact_match = bool(np.array_equal(target_array, predicted_array))
    pixel_accuracy = float(np.mean(target_array == predicted_array))

    target_foreground = target_array == FOREGROUND_COLOR
    predicted_foreground = predicted_array == FOREGROUND_COLOR
    union = np.logical_or(target_foreground, predicted_foreground)
    if not union.any():
        foreground_iou = 1.0
    else:
        intersection = np.logical_and(target_foreground, predicted_foreground)
        foreground_iou = float(intersection.sum() / union.sum())

    return EvaluationResult(
        exact_match=exact_match,
        pixel_accuracy=pixel_accuracy,
        foreground_iou=foreground_iou,
        parse_success=True,
        execution_success=True,
        error_type=None,
    )


def _load_target_image(path: Path) -> Image.Image:
    image = Image.open(path).convert("L")
    if image.size != (CANVAS_SIZE, CANVAS_SIZE):
        raise ValueError(
            f"Target image must be {CANVAS_SIZE}x{CANVAS_SIZE}, got {image.size[0]}x{image.size[1]}."
        )
    return image


from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage

from ui_bench.adapters.base import PredictionRequest, PredictionResult
from ui_bench.types import CANVAS_SIZE, FOREGROUND_COLOR


class HeuristicCVAdapter:
    """Classical-CV baseline.

    Thresholds the image, finds connected foreground components, and classifies
    each as a square or circle via bounding-box fill ratio, then hollow vs
    filled via morphological erosion. Emits one DSL primitive per component.
    """

    provider = "heuristic"

    def __init__(
        self,
        *,
        model: str = "heuristic-cv-v1",
        threshold: int = 128,
        min_area: int = 9,
        square_fill_threshold: float = 0.9,
        filled_erosion_threshold: float = 0.55,
        erosion_size: int = 3,
    ) -> None:
        self.model = model
        self.threshold = threshold
        self.min_area = min_area
        self.square_fill_threshold = square_fill_threshold
        self.filled_erosion_threshold = filled_erosion_threshold
        self.erosion_size = erosion_size

    def predict(self, request: PredictionRequest) -> PredictionResult:
        started = time.perf_counter()
        try:
            program = _infer_program(
                request.image_path,
                threshold=self.threshold,
                min_area=self.min_area,
                square_fill_threshold=self.square_fill_threshold,
                filled_erosion_threshold=self.filled_erosion_threshold,
                erosion_size=self.erosion_size,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return PredictionResult.from_error(
                model=self.model,
                error_type="heuristic_error",
                error_message=str(exc),
                latency_ms=latency_ms,
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        return PredictionResult(
            raw_text=program,
            normalized_text=program,
            model=self.model,
            request_id=None,
            usage=None,
            latency_ms=latency_ms,
            error_type=None,
            error_message=None,
        )

    def to_config(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "threshold": self.threshold,
            "min_area": self.min_area,
            "square_fill_threshold": self.square_fill_threshold,
            "filled_erosion_threshold": self.filled_erosion_threshold,
            "erosion_size": self.erosion_size,
        }


def _infer_program(
    image_path: Path,
    *,
    threshold: int,
    min_area: int,
    square_fill_threshold: float,
    filled_erosion_threshold: float,
    erosion_size: int,
) -> str:
    image = Image.open(image_path).convert("L")
    array = np.asarray(image, dtype=np.uint8)
    foreground = array == FOREGROUND_COLOR if FOREGROUND_COLOR == 0 else array <= threshold

    structure = np.ones((3, 3), dtype=bool)
    labels, count = ndimage.label(foreground, structure=structure)
    if count == 0:
        return ""

    eroded = ndimage.binary_erosion(foreground, structure=np.ones((erosion_size, erosion_size), dtype=bool))

    lines: list[str] = []
    for label_idx in range(1, count + 1):
        mask = labels == label_idx
        area = int(mask.sum())
        if area < min_area:
            continue

        ys, xs = np.where(mask)
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        if w < 2 or h < 2:
            continue

        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        extent = max(w, h)

        fill_ratio = area / (w * h)
        is_square = fill_ratio >= square_fill_threshold

        eroded_component_area = int((eroded & mask).sum())
        eroded_ratio = eroded_component_area / area if area else 0.0
        is_filled = eroded_ratio >= filled_erosion_threshold

        line = _emit_line(
            is_square=is_square,
            is_filled=is_filled,
            cx=cx,
            cy=cy,
            extent=extent,
            area=area,
        )
        if line:
            lines.append(line)

    return "\n".join(lines)


def _emit_line(*, is_square: bool, is_filled: bool, cx: int, cy: int, extent: int, area: int) -> str:
    cx = _clamp(cx, 0, CANVAS_SIZE - 1)
    cy = _clamp(cy, 0, CANVAS_SIZE - 1)
    extent = _clamp(extent, 1, CANVAS_SIZE)

    if is_square:
        if is_filled:
            return f"filled_square(cx={cx}, cy={cy}, size={extent})"
        stroke = _estimate_stroke(area=area, extent=extent, is_circle=False)
        max_stroke = max(1, (extent + 1) // 2)
        stroke = _clamp(stroke, 1, max_stroke)
        return f"square(cx={cx}, cy={cy}, size={extent}, stroke={stroke})"

    radius = max(1, extent // 2)
    if is_filled:
        return f"filled_circle(cx={cx}, cy={cy}, radius={radius})"
    stroke = _estimate_stroke(area=area, extent=extent, is_circle=True)
    stroke = _clamp(stroke, 1, radius)
    return f"circle(cx={cx}, cy={cy}, radius={radius}, stroke={stroke})"


def _estimate_stroke(*, area: int, extent: int, is_circle: bool) -> int:
    if is_circle:
        radius = max(1, extent // 2)
        perimeter = max(1.0, 2.0 * math.pi * radius)
    else:
        perimeter = max(1.0, 4.0 * extent)
    estimated = max(1, round(area / perimeter))
    return estimated


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))

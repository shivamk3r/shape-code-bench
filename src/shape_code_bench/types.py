from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal, TypeAlias

CANVAS_SIZE = 512
IMAGE_MODE = "L"
BACKGROUND_COLOR = 255
FOREGROUND_COLOR = 0
FUNCTION_NAMES = ("filled_circle", "circle", "filled_square", "square")

DifficultyName: TypeAlias = Literal["easy", "medium", "hard"]
Bounds: TypeAlias = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class FilledCircle:
    cx: int
    cy: int
    radius: int


@dataclass(frozen=True, slots=True)
class Circle:
    cx: int
    cy: int
    radius: int
    stroke: int


@dataclass(frozen=True, slots=True)
class FilledSquare:
    cx: int
    cy: int
    size: int


@dataclass(frozen=True, slots=True)
class Square:
    cx: int
    cy: int
    size: int
    stroke: int


Shape: TypeAlias = FilledCircle | Circle | FilledSquare | Square


@dataclass(frozen=True, slots=True)
class Scene:
    shapes: tuple[Shape, ...]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    exact_match: bool
    pixel_accuracy: float
    foreground_iou: float
    parse_success: bool
    execution_success: bool
    error_type: str | None

    def to_dict(self) -> dict[str, bool | float | str | None]:
        return {
            "exact_match": self.exact_match,
            "pixel_accuracy": self.pixel_accuracy,
            "foreground_iou": self.foreground_iou,
            "parse_success": self.parse_success,
            "execution_success": self.execution_success,
            "error_type": self.error_type,
        }


def shape_name(shape: Shape) -> str:
    if isinstance(shape, FilledCircle):
        return "filled_circle"
    if isinstance(shape, Circle):
        return "circle"
    if isinstance(shape, FilledSquare):
        return "filled_square"
    if isinstance(shape, Square):
        return "square"
    raise TypeError(f"Unsupported shape type: {type(shape)!r}")


def shape_kwargs(shape: Shape) -> dict[str, int]:
    if isinstance(shape, FilledCircle):
        return {"cx": shape.cx, "cy": shape.cy, "radius": shape.radius}
    if isinstance(shape, Circle):
        return {
            "cx": shape.cx,
            "cy": shape.cy,
            "radius": shape.radius,
            "stroke": shape.stroke,
        }
    if isinstance(shape, FilledSquare):
        return {"cx": shape.cx, "cy": shape.cy, "size": shape.size}
    if isinstance(shape, Square):
        return {"cx": shape.cx, "cy": shape.cy, "size": shape.size, "stroke": shape.stroke}
    raise TypeError(f"Unsupported shape type: {type(shape)!r}")


def shape_bounds(shape: Shape) -> Bounds:
    if isinstance(shape, (FilledCircle, Circle)):
        return (
            shape.cx - shape.radius,
            shape.cy - shape.radius,
            shape.cx + shape.radius,
            shape.cy + shape.radius,
        )
    if isinstance(shape, (FilledSquare, Square)):
        left = shape.cx - shape.size // 2
        top = shape.cy - shape.size // 2
        right = left + shape.size - 1
        bottom = top + shape.size - 1
        return (left, top, right, bottom)
    raise TypeError(f"Unsupported shape type: {type(shape)!r}")


def bbox_intersection_area(bounds_a: Bounds, bounds_b: Bounds) -> int:
    left = max(bounds_a[0], bounds_b[0])
    top = max(bounds_a[1], bounds_b[1])
    right = min(bounds_a[2], bounds_b[2])
    bottom = min(bounds_a[3], bounds_b[3])
    if left > right or top > bottom:
        return 0
    return (right - left + 1) * (bottom - top + 1)


def bbox_area(bounds: Bounds) -> int:
    return (bounds[2] - bounds[0] + 1) * (bounds[3] - bounds[1] + 1)


def bbox_iou(bounds_a: Bounds, bounds_b: Bounds) -> float:
    intersection = bbox_intersection_area(bounds_a, bounds_b)
    if intersection == 0:
        return 0.0
    union = bbox_area(bounds_a) + bbox_area(bounds_b) - intersection
    return intersection / union


def is_clipped(shape: Shape) -> bool:
    left, top, right, bottom = shape_bounds(shape)
    return left < 0 or top < 0 or right >= CANVAS_SIZE or bottom >= CANVAS_SIZE


def shape_inventory(scene: Scene) -> dict[str, int]:
    counts = Counter(shape_name(shape) for shape in scene.shapes)
    return {name: counts.get(name, 0) for name in FUNCTION_NAMES}


def render_config() -> dict[str, int | str]:
    return {
        "canvas_size": CANVAS_SIZE,
        "image_mode": IMAGE_MODE,
        "background_color": BACKGROUND_COLOR,
        "foreground_color": FOREGROUND_COLOR,
        "renderer_semantics": "v1-raster-pillow",
    }


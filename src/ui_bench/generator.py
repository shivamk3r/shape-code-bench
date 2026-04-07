from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from ui_bench.dsl import serialize_scene
from ui_bench.renderer import render_scene
from ui_bench.types import (
    CANVAS_SIZE,
    Circle,
    DifficultyName,
    FilledCircle,
    FilledSquare,
    Scene,
    Shape,
    Square,
    bbox_intersection_area,
    bbox_iou,
    is_clipped,
    render_config,
    shape_bounds,
    shape_inventory,
)


@dataclass(frozen=True, slots=True)
class DifficultySettings:
    min_shapes: int
    max_shapes: int
    min_extent: int
    max_extent: int
    min_stroke: int
    max_stroke: int
    clip_probability: float
    max_bbox_iou: float | None
    require_overlap: bool


DIFFICULTY_SETTINGS: dict[DifficultyName, DifficultySettings] = {
    "easy": DifficultySettings(
        min_shapes=1,
        max_shapes=3,
        min_extent=64,
        max_extent=160,
        min_stroke=2,
        max_stroke=6,
        clip_probability=0.0,
        max_bbox_iou=0.02,
        require_overlap=False,
    ),
    "medium": DifficultySettings(
        min_shapes=3,
        max_shapes=6,
        min_extent=32,
        max_extent=128,
        min_stroke=2,
        max_stroke=8,
        clip_probability=0.25,
        max_bbox_iou=0.35,
        require_overlap=False,
    ),
    "hard": DifficultySettings(
        min_shapes=6,
        max_shapes=10,
        min_extent=16,
        max_extent=128,
        min_stroke=1,
        max_stroke=10,
        clip_probability=1.0,
        max_bbox_iou=None,
        require_overlap=True,
    ),
}

SHAPE_TYPES = ("filled_circle", "circle", "filled_square", "square")
SMOKE_TEST_SAMPLE_SPECS: tuple[tuple[str, int], ...] = (("easy", 101), ("medium", 202))


def generate_scene(difficulty: str, seed: int) -> Scene:
    try:
        settings = DIFFICULTY_SETTINGS[difficulty]  # type: ignore[index]
    except KeyError as exc:
        expected = ", ".join(DIFFICULTY_SETTINGS)
        raise ValueError(f"Unsupported difficulty '{difficulty}'. Expected one of: {expected}.") from exc

    rng = random.Random(seed)
    for _ in range(200):
        scene = _generate_candidate_scene(rng, settings)
        if _scene_is_valid(scene, settings):
            return scene
    raise RuntimeError(f"Failed to generate a valid '{difficulty}' scene for seed {seed}.")


def sample_id(split: str, difficulty: str, seed: int) -> str:
    return f"{split}-{difficulty}-{seed:08d}"


def build_sample_metadata(split: str, difficulty: str, seed: int, scene: Scene, program: str) -> dict[str, object]:
    return {
        "sample_id": sample_id(split, difficulty, seed),
        "split": split,
        "difficulty": difficulty,
        "seed": seed,
        "image_size": CANVAS_SIZE,
        "num_shapes": len(scene.shapes),
        "shape_inventory": shape_inventory(scene),
        "ground_truth_program": program,
        "render_config": render_config(),
    }


def write_generated_sample(split: str, difficulty: str, seed: int, output_dir: str) -> dict[str, str]:
    scene = generate_scene(difficulty, seed)
    program = serialize_scene(scene)
    image = render_scene(scene)
    current_sample_id = sample_id(split, difficulty, seed)

    output_root = Path(output_dir) / split / difficulty
    output_root.mkdir(parents=True, exist_ok=True)

    image_path = output_root / f"{current_sample_id}.png"
    metadata_path = output_root / f"{current_sample_id}.json"

    image.save(image_path)
    metadata = build_sample_metadata(split, difficulty, seed, scene, program)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "sample_id": current_sample_id,
        "image_path": str(image_path),
        "metadata_path": str(metadata_path),
    }


def write_smoke_test_dataset(output_dir: str, split: str = "smoke") -> list[dict[str, str]]:
    return [
        write_generated_sample(split=split, difficulty=difficulty, seed=seed, output_dir=output_dir)
        for difficulty, seed in SMOKE_TEST_SAMPLE_SPECS
    ]


def _generate_candidate_scene(rng: random.Random, settings: DifficultySettings) -> Scene:
    shapes: list[Shape] = []
    shape_count = rng.randint(settings.min_shapes, settings.max_shapes)
    for _ in range(shape_count):
        shapes.append(_sample_shape_with_rejection(rng, settings, shapes))
    return Scene(tuple(shapes))


def _sample_shape_with_rejection(
    rng: random.Random,
    settings: DifficultySettings,
    existing_shapes: list[Shape],
) -> Shape:
    for _ in range(500):
        shape = _sample_shape(rng, settings)
        if _shape_is_valid(shape, existing_shapes, settings):
            return shape
    raise RuntimeError("Unable to place a shape that satisfies the current difficulty constraints.")


def _sample_shape(rng: random.Random, settings: DifficultySettings) -> Shape:
    shape_type = rng.choice(SHAPE_TYPES)
    extent = rng.randint(settings.min_extent, settings.max_extent)

    if shape_type.endswith("circle"):
        cx, cy = _sample_center(rng, shape_type, extent, settings.clip_probability)
        if shape_type == "filled_circle":
            return FilledCircle(cx=cx, cy=cy, radius=extent)
        stroke = _sample_stroke(rng, settings, extent)
        return Circle(cx=cx, cy=cy, radius=extent, stroke=stroke)

    cx, cy = _sample_center(rng, shape_type, extent, settings.clip_probability)
    if shape_type == "filled_square":
        return FilledSquare(cx=cx, cy=cy, size=extent)
    stroke = _sample_stroke(rng, settings, max(1, (extent + 1) // 2))
    return Square(cx=cx, cy=cy, size=extent, stroke=stroke)


def _sample_center(
    rng: random.Random,
    shape_type: str,
    extent: int,
    clip_probability: float,
) -> tuple[int, int]:
    if clip_probability < 1.0 and rng.random() >= clip_probability:
        min_center_x, max_center_x = _interior_center_range(shape_type, extent, axis="x")
        min_center_y, max_center_y = _interior_center_range(shape_type, extent, axis="y")
        return (
            rng.randint(min_center_x, max_center_x),
            rng.randint(min_center_y, max_center_y),
        )
    return (
        rng.randint(0, CANVAS_SIZE - 1),
        rng.randint(0, CANVAS_SIZE - 1),
    )


def _interior_center_range(shape_type: str, extent: int, axis: str) -> tuple[int, int]:
    del axis
    if shape_type.endswith("circle"):
        return (extent, CANVAS_SIZE - 1 - extent)

    min_center = extent // 2
    max_center = CANVAS_SIZE - extent + extent // 2
    return (min_center, max_center)


def _sample_stroke(rng: random.Random, settings: DifficultySettings, max_supported: int) -> int:
    upper_bound = min(settings.max_stroke, max_supported)
    lower_bound = min(settings.min_stroke, upper_bound)
    return rng.randint(lower_bound, upper_bound)


def _shape_is_valid(shape: Shape, existing_shapes: list[Shape], settings: DifficultySettings) -> bool:
    if settings.clip_probability == 0.0 and is_clipped(shape):
        return False

    if settings.max_bbox_iou is None:
        return True

    bounds = shape_bounds(shape)
    for existing_shape in existing_shapes:
        if bbox_iou(bounds, shape_bounds(existing_shape)) > settings.max_bbox_iou:
            return False
    return True


def _scene_is_valid(scene: Scene, settings: DifficultySettings) -> bool:
    if settings.clip_probability == 0.0 and any(is_clipped(shape) for shape in scene.shapes):
        return False

    if settings.require_overlap and not _has_overlap(scene):
        return False
    return True


def _has_overlap(scene: Scene) -> bool:
    bounds = [shape_bounds(shape) for shape in scene.shapes]
    for index, current in enumerate(bounds):
        for other in bounds[index + 1 :]:
            if bbox_intersection_area(current, other) > 0:
                return True
    return False

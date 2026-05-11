from __future__ import annotations

from shape_code_bench.generator import generate_scene
from shape_code_bench.types import Circle, FilledCircle, Square, bbox_intersection_area, bbox_iou
from shape_code_bench.types import is_clipped, shape_bounds


def test_generate_scene_is_reproducible() -> None:
    assert generate_scene("medium", seed=42) == generate_scene("medium", seed=42)


def test_easy_scene_stays_within_v1_bounds() -> None:
    scene = generate_scene("easy", seed=7)

    assert 1 <= len(scene.shapes) <= 3
    assert all(not is_clipped(shape) for shape in scene.shapes)

    for shape in scene.shapes:
        if isinstance(shape, (FilledCircle, Circle)):
            assert 64 <= shape.radius <= 160
        else:
            assert 64 <= shape.size <= 160

        if isinstance(shape, (Circle, Square)):
            assert 2 <= shape.stroke <= 6

    bounds = [shape_bounds(shape) for shape in scene.shapes]
    for index, current in enumerate(bounds):
        for other in bounds[index + 1 :]:
            assert bbox_iou(current, other) <= 0.02


def test_medium_scene_stays_within_v1_bounds() -> None:
    scene = generate_scene("medium", seed=13)

    assert 3 <= len(scene.shapes) <= 6

    for shape in scene.shapes:
        if isinstance(shape, (FilledCircle, Circle)):
            assert 32 <= shape.radius <= 128
        else:
            assert 32 <= shape.size <= 128

        if isinstance(shape, (Circle, Square)):
            assert 2 <= shape.stroke <= 8


def test_hard_scene_requires_overlap_and_uses_hard_ranges() -> None:
    scene = generate_scene("hard", seed=99)

    assert 6 <= len(scene.shapes) <= 10

    has_overlap = False
    bounds = [shape_bounds(shape) for shape in scene.shapes]
    for index, current in enumerate(bounds):
        for other in bounds[index + 1 :]:
            if bbox_intersection_area(current, other) > 0:
                has_overlap = True

    assert has_overlap

    for shape in scene.shapes:
        if isinstance(shape, (FilledCircle, Circle)):
            assert 16 <= shape.radius <= 128
        else:
            assert 16 <= shape.size <= 128

        if isinstance(shape, (Circle, Square)):
            assert 1 <= shape.stroke <= 10

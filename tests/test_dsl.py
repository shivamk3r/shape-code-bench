from __future__ import annotations

import pytest

from ui_bench.dsl import DSLValidationError, parse_program, serialize_scene
from ui_bench.types import Circle, FilledCircle, FilledSquare, Scene, Square


def test_parse_valid_program() -> None:
    scene = parse_program(
        "\n".join(
            [
                "filled_circle(cx=128, cy=128, radius=40)",
                "circle(cx=300, cy=220, radius=60, stroke=4)",
                "filled_square(cx=220, cy=360, size=81)",
                "square(cx=380, cy=120, size=80, stroke=3)",
            ]
        )
    )

    assert scene == Scene(
        shapes=(
            FilledCircle(cx=128, cy=128, radius=40),
            Circle(cx=300, cy=220, radius=60, stroke=4),
            FilledSquare(cx=220, cy=360, size=81),
            Square(cx=380, cy=120, size=80, stroke=3),
        )
    )


@pytest.mark.parametrize(
    ("program", "error_type"),
    [
        ("import math", "top_level_only"),
        ("x = 1", "top_level_only"),
        ("circle(1, cy=10, radius=20, stroke=2)", "positional_arguments"),
        ("triangle(cx=10, cy=10, size=20)", "unsupported_function"),
        ("circle(cx=10 + 1, cy=10, radius=20, stroke=2)", "non_literal_argument"),
        ("circle(cx=10, cy=10, radius=20, stroke=2, stroke=3)", "duplicate_argument"),
        ("filled_circle(cx=10, cy=10)", "missing_argument"),
        ("filled_square(cx=10, cy=10, size=20, stroke=2)", "unexpected_argument"),
        ("square(cx=-1, cy=10, size=20, stroke=2)", "out_of_range"),
        ("circle(cx=10, cy=10, radius=20, stroke=40)", "invalid_stroke"),
        ("", "empty_program"),
    ],
)
def test_parse_rejects_invalid_programs(program: str, error_type: str) -> None:
    with pytest.raises(DSLValidationError) as exc_info:
        parse_program(program)

    assert exc_info.value.error_type == error_type


def test_serialize_round_trip_to_canonical_format() -> None:
    source = "\n".join(
        [
            "circle(stroke=4, cy=220, radius=60, cx=300)",
            "filled_square(size=81, cx=220, cy=360)",
        ]
    )

    scene = parse_program(source)

    assert serialize_scene(scene) == "\n".join(
        [
            "circle(cx=300, cy=220, radius=60, stroke=4)",
            "filled_square(cx=220, cy=360, size=81)",
        ]
    )


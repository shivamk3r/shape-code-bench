from __future__ import annotations

import pytest

from shape_code_bench.normalization import normalize_prediction_text


def test_empty_input_returns_empty() -> None:
    assert normalize_prediction_text("") == ""
    assert normalize_prediction_text("   \n  ") == ""


def test_bare_primitive_lines_pass_through() -> None:
    body = "filled_circle(cx=10, cy=10, radius=4)\nfilled_square(cx=20, cy=20, size=8)"
    assert normalize_prediction_text(body) == body


def test_fenced_block_anywhere_is_extracted() -> None:
    text = (
        "Sure, here is the DSL that reconstructs the image:\n"
        "\n"
        "```python\n"
        "filled_circle(cx=128, cy=128, radius=40)\n"
        "circle(cx=300, cy=220, radius=60, stroke=4)\n"
        "```\n"
        "\n"
        "Let me know if you want adjustments."
    )
    assert normalize_prediction_text(text) == (
        "filled_circle(cx=128, cy=128, radius=40)\n"
        "circle(cx=300, cy=220, radius=60, stroke=4)"
    )


def test_untagged_fence_works() -> None:
    text = "```\nfilled_square(cx=5, cy=5, size=3)\n```"
    assert normalize_prediction_text(text) == "filled_square(cx=5, cy=5, size=3)"


def test_prose_only_returns_raw_text_for_honest_parse_error() -> None:
    text = "I cannot answer this question with visual code."
    assert normalize_prediction_text(text) == text


def test_prose_with_inline_primitives_filters_out_prose() -> None:
    text = (
        "Here is my analysis:\n"
        "I see a circle and a square.\n"
        "filled_circle(cx=100, cy=100, radius=30)\n"
        "filled_square(cx=200, cy=200, size=40)\n"
        "Hope that helps!"
    )
    assert normalize_prediction_text(text) == (
        "filled_circle(cx=100, cy=100, radius=30)\n"
        "filled_square(cx=200, cy=200, size=40)"
    )


def test_fence_is_preferred_over_bare_lines() -> None:
    text = (
        "filled_circle(cx=1, cy=1, radius=1)\n"
        "```\n"
        "filled_square(cx=5, cy=5, size=3)\n"
        "```\n"
    )
    assert normalize_prediction_text(text) == "filled_square(cx=5, cy=5, size=3)"


@pytest.mark.parametrize(
    "line",
    [
        "  filled_circle(cx=10, cy=10, radius=4)  ",
        "\tfilled_square(cx=1, cy=1, size=2)",
    ],
)
def test_primitive_lines_tolerate_whitespace(line: str) -> None:
    assert normalize_prediction_text(line) == line.strip()

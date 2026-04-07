from __future__ import annotations

import ast

from ui_bench.types import CANVAS_SIZE, Circle, FilledCircle, FilledSquare, Scene, Shape, Square
from ui_bench.types import shape_kwargs, shape_name

FUNCTION_ARGUMENTS = {
    "filled_circle": ("cx", "cy", "radius"),
    "circle": ("cx", "cy", "radius", "stroke"),
    "filled_square": ("cx", "cy", "size"),
    "square": ("cx", "cy", "size", "stroke"),
}


class DSLValidationError(ValueError):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


def parse_program(text: str) -> Scene:
    if not text.strip():
        raise DSLValidationError("empty_program", "Program must contain at least one function call.")

    try:
        module = ast.parse(text, mode="exec")
    except SyntaxError as exc:
        raise DSLValidationError("syntax_error", f"Invalid syntax: {exc.msg}.") from exc

    shapes: list[Shape] = []
    for statement in module.body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            raise DSLValidationError(
                "top_level_only",
                "Program must contain only top-level function calls.",
            )

        call = statement.value
        if not isinstance(call.func, ast.Name):
            raise DSLValidationError("invalid_function", "Function names must be bare identifiers.")

        function_name = call.func.id
        if function_name not in FUNCTION_ARGUMENTS:
            raise DSLValidationError(
                "unsupported_function",
                f"Unsupported function '{function_name}'.",
            )

        if call.args:
            raise DSLValidationError(
                "positional_arguments",
                "Only keyword arguments are allowed.",
            )

        keyword_values: dict[str, int] = {}
        for keyword in call.keywords:
            if keyword.arg is None:
                raise DSLValidationError(
                    "invalid_keyword_argument",
                    "Starred keyword arguments are not allowed.",
                )
            if keyword.arg in keyword_values:
                raise DSLValidationError(
                    "duplicate_argument",
                    f"Duplicate argument '{keyword.arg}'.",
                )
            keyword_values[keyword.arg] = _literal_int(keyword.value, keyword.arg)

        required_arguments = FUNCTION_ARGUMENTS[function_name]
        unexpected_arguments = sorted(set(keyword_values) - set(required_arguments))
        if unexpected_arguments:
            raise DSLValidationError(
                "unexpected_argument",
                f"Unexpected arguments for '{function_name}': {', '.join(unexpected_arguments)}.",
            )

        missing_arguments = [name for name in required_arguments if name not in keyword_values]
        if missing_arguments:
            raise DSLValidationError(
                "missing_argument",
                f"Missing arguments for '{function_name}': {', '.join(missing_arguments)}.",
            )

        shapes.append(_build_shape(function_name, keyword_values))

    return Scene(tuple(shapes))


def serialize_scene(scene: Scene) -> str:
    lines: list[str] = []
    for shape in scene.shapes:
        name = shape_name(shape)
        kwargs = shape_kwargs(shape)
        ordered_arguments = ", ".join(f"{arg}={kwargs[arg]}" for arg in FUNCTION_ARGUMENTS[name])
        lines.append(f"{name}({ordered_arguments})")
    return "\n".join(lines)


def _literal_int(node: ast.AST, argument_name: str) -> int:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        value = node.operand.value
        return value if isinstance(node.op, ast.UAdd) else -value
    raise DSLValidationError(
        "non_literal_argument",
        f"Argument '{argument_name}' must be an integer literal.",
    )


def _build_shape(function_name: str, kwargs: dict[str, int]) -> Shape:
    cx = _validate_coordinate("cx", kwargs["cx"])
    cy = _validate_coordinate("cy", kwargs["cy"])

    if function_name == "filled_circle":
        return FilledCircle(cx=cx, cy=cy, radius=_validate_extent("radius", kwargs["radius"]))
    if function_name == "circle":
        radius = _validate_extent("radius", kwargs["radius"])
        stroke = _validate_stroke("circle", kwargs["stroke"], radius)
        return Circle(cx=cx, cy=cy, radius=radius, stroke=stroke)
    if function_name == "filled_square":
        return FilledSquare(cx=cx, cy=cy, size=_validate_extent("size", kwargs["size"]))
    if function_name == "square":
        size = _validate_extent("size", kwargs["size"])
        stroke = _validate_stroke("square", kwargs["stroke"], size)
        return Square(cx=cx, cy=cy, size=size, stroke=stroke)
    raise DSLValidationError("unsupported_function", f"Unsupported function '{function_name}'.")


def _validate_coordinate(name: str, value: int) -> int:
    if 0 <= value < CANVAS_SIZE:
        return value
    raise DSLValidationError(
        "out_of_range",
        f"Argument '{name}' must be in the range [0, {CANVAS_SIZE - 1}].",
    )


def _validate_extent(name: str, value: int) -> int:
    if 1 <= value <= CANVAS_SIZE:
        return value
    raise DSLValidationError(
        "out_of_range",
        f"Argument '{name}' must be in the range [1, {CANVAS_SIZE}].",
    )


def _validate_stroke(shape_type: str, stroke: int, extent: int) -> int:
    if stroke < 1:
        raise DSLValidationError("invalid_stroke", "Stroke must be at least 1 pixel.")

    if shape_type == "circle":
        max_stroke = extent
    else:
        max_stroke = max(1, (extent + 1) // 2)

    if stroke > max_stroke:
        raise DSLValidationError(
            "invalid_stroke",
            f"Stroke {stroke} exceeds the maximum supported width {max_stroke} for {shape_type}.",
        )
    return stroke


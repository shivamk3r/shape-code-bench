"""Core package for the ui-bench benchmark."""

from ui_bench.dsl import DSLValidationError, parse_program, serialize_scene
from ui_bench.evaluator import evaluate_program
from ui_bench.generator import generate_scene
from ui_bench.renderer import render_scene

__all__ = [
    "DSLValidationError",
    "evaluate_program",
    "generate_scene",
    "parse_program",
    "render_scene",
    "serialize_scene",
]


"""Core package for the ui-bench benchmark."""

from ui_bench.adapters import (
    DEFAULT_IMAGE_DETAIL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    ModelAdapter,
    OpenAIResponsesAdapter,
    PredictionRequest,
    PredictionResult,
)
from ui_bench.dsl import DSLValidationError, parse_program, serialize_scene
from ui_bench.evaluator import evaluate_program
from ui_bench.generator import generate_scene, write_generated_sample, write_smoke_test_dataset
from ui_bench.renderer import render_scene
from ui_bench.runner import BenchmarkRunResult, run_benchmark

__all__ = [
    "BenchmarkRunResult",
    "DEFAULT_IMAGE_DETAIL",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_REASONING_EFFORT",
    "DSLValidationError",
    "ModelAdapter",
    "OpenAIResponsesAdapter",
    "PredictionRequest",
    "PredictionResult",
    "evaluate_program",
    "generate_scene",
    "parse_program",
    "render_scene",
    "run_benchmark",
    "serialize_scene",
    "write_generated_sample",
    "write_smoke_test_dataset",
]

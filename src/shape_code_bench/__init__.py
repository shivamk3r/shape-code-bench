"""Core package for the ShapeCodeBench benchmark."""

from shape_code_bench.adapters import (
    DEFAULT_IMAGE_DETAIL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    ModelAdapter,
    OpenAIResponsesAdapter,
    PredictionRequest,
    PredictionResult,
)
from shape_code_bench.dsl import DSLValidationError, parse_program, serialize_scene
from shape_code_bench.evaluator import evaluate_program
from shape_code_bench.generator import generate_scene, write_generated_sample, write_smoke_test_dataset
from shape_code_bench.renderer import render_scene
from shape_code_bench.runner import BenchmarkRunResult, run_benchmark

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

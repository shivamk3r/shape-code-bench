"""Model adapter interfaces and implementations for ui-bench."""

from ui_bench.adapters.base import ModelAdapter, PredictionRequest, PredictionResult
from ui_bench.adapters.openai_adapter import (
    DEFAULT_IMAGE_DETAIL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    OpenAIResponsesAdapter,
)

__all__ = [
    "DEFAULT_IMAGE_DETAIL",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_REASONING_EFFORT",
    "ModelAdapter",
    "OpenAIResponsesAdapter",
    "PredictionRequest",
    "PredictionResult",
]


from __future__ import annotations

import time
from typing import Any

from ui_bench.adapters.base import PredictionRequest, PredictionResult


class EmptyProgramAdapter:
    """Floor baseline that always predicts an empty program."""

    provider = "empty"

    def __init__(self, *, model: str = "empty-program") -> None:
        self.model = model

    def predict(self, request: PredictionRequest) -> PredictionResult:
        del request
        started = time.perf_counter()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return PredictionResult(
            raw_text="",
            normalized_text="",
            model=self.model,
            request_id=None,
            usage=None,
            latency_ms=latency_ms,
            error_type=None,
            error_message=None,
        )

    def to_config(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model}

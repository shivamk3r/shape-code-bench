from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PredictionRequest:
    sample_id: str
    image_path: Path
    system_instruction: str
    prompt_text: str

    def to_dict(self) -> dict[str, str]:
        return {
            "sample_id": self.sample_id,
            "image_path": str(self.image_path),
            "system_instruction": self.system_instruction,
            "prompt_text": self.prompt_text,
        }


@dataclass(frozen=True, slots=True)
class PredictionResult:
    raw_text: str
    normalized_text: str
    model: str
    request_id: str | None
    usage: dict[str, Any] | None
    latency_ms: int
    error_type: str | None
    error_message: str | None = None

    @classmethod
    def from_error(
        cls,
        *,
        model: str,
        error_type: str,
        error_message: str,
        latency_ms: int = 0,
    ) -> PredictionResult:
        return cls(
            raw_text="",
            normalized_text="",
            model=model,
            request_id=None,
            usage=None,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "model": self.model,
            "request_id": self.request_id,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


class ModelAdapter(Protocol):
    provider: str
    model: str

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Generate one prediction for a single benchmark sample."""

    def to_config(self) -> dict[str, Any]:
        """Return serializable adapter configuration for run artifacts."""


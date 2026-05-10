from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import openai
from dotenv import load_dotenv
from openai import OpenAI

from ui_bench.adapters.base import PredictionRequest, PredictionResult
from ui_bench.normalization import normalize_prediction_text

DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_IMAGE_DETAIL = "low"
DEFAULT_MAX_OUTPUT_TOKENS = 256


class OpenAIResponsesAdapter:
    provider = "openai"

    def __init__(
        self,
        *,
        model: str = DEFAULT_OPENAI_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        image_detail: str = DEFAULT_IMAGE_DETAIL,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        api_key: str | None = None,
        client: OpenAI | Any | None = None,
    ) -> None:
        load_dotenv(override=False)

        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if client is None and not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is not set. Add it to the environment or .env.")

        self.model = model
        self.reasoning_effort = reasoning_effort
        self.image_detail = image_detail
        self.max_output_tokens = max_output_tokens
        self._client = client or OpenAI(api_key=resolved_api_key)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        started = time.perf_counter()
        data_url = _encode_image_as_data_url(request.image_path)

        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=request.system_instruction,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=self.max_output_tokens,
                text={"verbosity": "low"},
                store=False,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": request.prompt_text},
                            {
                                "type": "input_image",
                                "image_url": data_url,
                                "detail": self.image_detail,
                            },
                        ],
                    }
                ],
            )
        except openai.AuthenticationError as exc:
            return self._error_result("authentication_error", exc, started)
        except openai.RateLimitError as exc:
            return self._error_result("rate_limit_error", exc, started)
        except openai.APIConnectionError as exc:
            return self._error_result("connection_error", exc, started)
        except openai.BadRequestError as exc:
            return self._error_result("bad_request_error", exc, started)
        except openai.APIStatusError as exc:
            return self._error_result("api_status_error", exc, started)
        except Exception as exc:
            return self._error_result("unexpected_adapter_error", exc, started)

        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_text = getattr(response, "output_text", "") or ""
        status = getattr(response, "status", None)
        incomplete_details = getattr(response, "incomplete_details", None)
        if not raw_text and status == "incomplete":
            reason = getattr(incomplete_details, "reason", "unknown")
            return PredictionResult(
                raw_text="",
                normalized_text="",
                model=self.model,
                request_id=getattr(response, "id", None),
                usage=_serialize_usage(getattr(response, "usage", None)),
                latency_ms=latency_ms,
                error_type="incomplete_response",
                error_message=f"Response incomplete before visible text: {reason}",
            )

        return PredictionResult(
            raw_text=raw_text,
            normalized_text=normalize_prediction_text(raw_text),
            model=self.model,
            request_id=getattr(response, "id", None),
            usage=_serialize_usage(getattr(response, "usage", None)),
            latency_ms=latency_ms,
            error_type=None,
            error_message=None,
        )

    def to_config(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "image_detail": self.image_detail,
            "max_output_tokens": self.max_output_tokens,
        }

    def _error_result(self, error_type: str, exc: Exception, started: float) -> PredictionResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return PredictionResult.from_error(
            model=self.model,
            error_type=error_type,
            error_message=str(exc),
            latency_ms=latency_ms,
        )


def _encode_image_as_data_url(path: Path) -> str:
    image_bytes = path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _serialize_usage(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {"value": str(usage)}

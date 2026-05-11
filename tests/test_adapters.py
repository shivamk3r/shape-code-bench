from __future__ import annotations

from pathlib import Path

import httpx
import openai

from shape_code_bench.adapters import OpenAIResponsesAdapter, PredictionRequest
from shape_code_bench.generator import write_generated_sample


class FakeUsage:
    def model_dump(self) -> dict[str, int]:
        return {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}


class FakeResponse:
    def __init__(self, output_text: str | None) -> None:
        self.id = "resp_123"
        self.output_text = output_text
        self.usage = FakeUsage()


class RecordingResponsesAPI:
    def __init__(self, *, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._response = response
        self._error = error

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class FakeClient:
    def __init__(self, *, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.responses = RecordingResponsesAPI(response=response, error=error)


def test_openai_adapter_successful_prediction(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    fake_client = FakeClient(response=FakeResponse("filled_circle(cx=10, cy=10, radius=4)"))
    adapter = OpenAIResponsesAdapter(client=fake_client, model="test-model")

    result = adapter.predict(request)

    assert result.raw_text == "filled_circle(cx=10, cy=10, radius=4)"
    assert result.normalized_text == "filled_circle(cx=10, cy=10, radius=4)"
    assert result.model == "test-model"
    assert result.request_id == "resp_123"
    assert result.usage == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert result.error_type is None
    assert result.latency_ms >= 0

    call = fake_client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["reasoning"] == {"effort": "low"}
    assert call["max_output_tokens"] == 256
    content = call["input"][0]["content"]  # type: ignore[index]
    assert content[0]["type"] == "input_text"  # type: ignore[index]
    assert content[1]["type"] == "input_image"  # type: ignore[index]
    assert content[1]["detail"] == "low"  # type: ignore[index]
    assert content[1]["image_url"].startswith("data:image/png;base64,")  # type: ignore[index]


def test_openai_adapter_normalizes_fenced_output(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    fake_client = FakeClient(response=FakeResponse("```python\nfilled_square(cx=9, cy=9, size=6)\n```"))
    adapter = OpenAIResponsesAdapter(client=fake_client, model="test-model")

    result = adapter.predict(request)

    assert result.raw_text.startswith("```python")
    assert result.normalized_text == "filled_square(cx=9, cy=9, size=6)"


def test_openai_adapter_handles_empty_output(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    fake_client = FakeClient(response=FakeResponse(None))
    adapter = OpenAIResponsesAdapter(client=fake_client, model="test-model")

    result = adapter.predict(request)

    assert result.raw_text == ""
    assert result.normalized_text == ""
    assert result.error_type is None


def test_openai_adapter_maps_expected_errors(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    request_obj = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response_obj = httpx.Response(429, request=request_obj)
    error_cases = [
        (
            "authentication_error",
            openai.AuthenticationError("bad key", response=httpx.Response(401, request=request_obj), body={}),
        ),
        (
            "rate_limit_error",
            openai.RateLimitError("slow down", response=response_obj, body={}),
        ),
        (
            "connection_error",
            openai.APIConnectionError(message="network", request=request_obj),
        ),
        (
            "bad_request_error",
            openai.BadRequestError("bad request", response=httpx.Response(400, request=request_obj), body={}),
        ),
        (
            "api_status_error",
            openai.APIStatusError("server", response=httpx.Response(500, request=request_obj), body={}),
        ),
    ]

    for expected_error_type, error in error_cases:
        fake_client = FakeClient(error=error)
        adapter = OpenAIResponsesAdapter(client=fake_client, model="test-model")

        result = adapter.predict(request)

        assert result.error_type == expected_error_type
        assert result.normalized_text == ""
        assert result.request_id is None


def _build_request(tmp_path: Path) -> PredictionRequest:
    generated = write_generated_sample(split="train", difficulty="easy", seed=5, output_dir=str(tmp_path / "generated"))
    return PredictionRequest(
        sample_id=generated["sample_id"],
        image_path=Path(generated["image_path"]),
        system_instruction="Return code only.",
        prompt_text="Use the DSL.",
    )

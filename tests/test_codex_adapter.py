from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ui_bench.adapters import CodexAdapter, PredictionRequest
from ui_bench.generator import write_generated_sample


class FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


class FakeRunner:
    """Callable stand-in for ``subprocess.run``. Records argv and writes a canned output file."""

    def __init__(
        self,
        *,
        output_body: str | None = "filled_circle(cx=10, cy=10, radius=4)",
        returncode: int = 0,
        stderr: str = "",
        exception: Exception | None = None,
    ) -> None:
        self.output_body = output_body
        self.returncode = returncode
        self.stderr = stderr
        self.exception = exception
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeCompleted:
        self.calls.append(list(argv))
        if self.exception is not None:
            raise self.exception

        if self.output_body is not None and self.returncode == 0:
            output_path = Path(argv[argv.index("-o") + 1])
            output_path.write_text(self.output_body, encoding="utf-8")

        return FakeCompleted(returncode=self.returncode, stderr=self.stderr)


def test_codex_adapter_builds_expected_argv_and_returns_normalized(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(output_body="Here is the DSL:\n\n```\nfilled_circle(cx=10, cy=10, radius=4)\n```")
    adapter = CodexAdapter(model="gpt-5.4", subprocess_run=runner)

    result = adapter.predict(request)

    assert result.error_type is None
    assert result.model == "gpt-5.4"
    assert result.normalized_text == "filled_circle(cx=10, cy=10, radius=4)"
    assert result.raw_text.startswith("Here is the DSL")
    assert result.request_id is None
    assert result.usage is None
    assert result.latency_ms >= 0

    assert len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv[0] == "codex"
    assert argv[1] == "exec"
    assert "--skip-git-repo-check" in argv
    assert "--ephemeral" in argv
    assert argv[argv.index("-s") + 1] == "read-only"
    assert argv[argv.index("-m") + 1] == "gpt-5.4"
    assert argv[argv.index("-i") + 1] == str(request.image_path)
    assert argv[-1] == f"{request.system_instruction}\n\n{request.prompt_text}"


def test_codex_adapter_classifies_timeout(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(exception=subprocess.TimeoutExpired(cmd="codex", timeout=1))
    adapter = CodexAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "timeout"
    assert result.normalized_text == ""


def test_codex_adapter_classifies_missing_binary(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(exception=FileNotFoundError("codex: not found"))
    adapter = CodexAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "codex_binary_missing"


def test_codex_adapter_classifies_login_required(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(returncode=1, stderr="Error: not logged in. Please run `codex login`.")
    adapter = CodexAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "login_required"
    assert "not logged in" in (result.error_message or "")


def test_codex_adapter_classifies_process_failure(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(returncode=2, stderr="Error: model gpt-9 not recognized.")
    adapter = CodexAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "process_failure"
    assert "gpt-9" in (result.error_message or "")


def test_codex_adapter_classifies_empty_output(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(output_body="")
    adapter = CodexAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "empty_output"


def test_codex_adapter_retries_on_transient_failure(tmp_path: Path) -> None:
    request = _build_request(tmp_path)

    class FlakyRunner:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, argv: list[str], **kwargs: Any) -> FakeCompleted:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(cmd="codex", timeout=1)
            output_path = Path(argv[argv.index("-o") + 1])
            output_path.write_text("filled_square(cx=5, cy=5, size=3)\n", encoding="utf-8")
            return FakeCompleted(returncode=0, stderr="")

    runner = FlakyRunner()
    adapter = CodexAdapter(subprocess_run=runner, max_retries=2)

    # Patch time.sleep to avoid burning real time during retries.
    import ui_bench.adapters.codex_adapter as codex_module

    original_sleep = codex_module.time.sleep
    codex_module.time.sleep = lambda _: None
    try:
        result = adapter.predict(request)
    finally:
        codex_module.time.sleep = original_sleep

    assert runner.calls == 2
    assert result.error_type is None
    assert result.normalized_text == "filled_square(cx=5, cy=5, size=3)"


def test_codex_adapter_to_config_is_serializable() -> None:
    adapter = CodexAdapter(
        model="gpt-5.3-codex",
        sandbox="read-only",
        timeout_seconds=90,
        max_retries=1,
        extra_args=("--foo", "bar"),
    )

    config = adapter.to_config()

    assert config == {
        "provider": "codex",
        "model": "gpt-5.3-codex",
        "sandbox": "read-only",
        "timeout_seconds": 90,
        "codex_binary": "codex",
        "max_retries": 1,
        "extra_args": ["--foo", "bar"],
    }


def test_codex_adapter_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError):
        CodexAdapter(timeout_seconds=0)


def _build_request(tmp_path: Path) -> PredictionRequest:
    generated = write_generated_sample(
        split="train",
        difficulty="easy",
        seed=5,
        output_dir=str(tmp_path / "generated"),
    )
    return PredictionRequest(
        sample_id=generated["sample_id"],
        image_path=Path(generated["image_path"]),
        system_instruction="Return only DSL.",
        prompt_text="Reconstruct the image.",
    )

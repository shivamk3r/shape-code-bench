from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ui_bench.adapters import ClaudeCodeAdapter, PredictionRequest
from ui_bench.generator import write_generated_sample


class FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    """Callable stand-in for ``subprocess.run``. Records argv and returns canned stdout."""

    def __init__(
        self,
        *,
        stdout: str = "filled_circle(cx=10, cy=10, radius=4)",
        returncode: int = 0,
        stderr: str = "",
        exception: Exception | None = None,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.exception = exception
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeCompleted:
        self.calls.append(list(argv))
        if self.exception is not None:
            raise self.exception
        return FakeCompleted(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_claude_adapter_builds_expected_argv_and_returns_normalized(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(stdout="Here is the DSL:\n\n```\nfilled_circle(cx=10, cy=10, radius=4)\n```")
    adapter = ClaudeCodeAdapter(model="claude-opus-4-7[1m]", effort="max", subprocess_run=runner)

    result = adapter.predict(request)

    assert result.error_type is None
    assert result.model == "claude-opus-4-7[1m]"
    assert result.normalized_text == "filled_circle(cx=10, cy=10, radius=4)"
    assert result.raw_text.startswith("Here is the DSL")
    assert result.latency_ms >= 0

    assert len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv[0] == "claude"
    assert "--print" in argv
    assert argv[argv.index("--model") + 1] == "claude-opus-4-7[1m]"
    assert argv[argv.index("--effort") + 1] == "max"
    assert argv[argv.index("--output-format") + 1] == "text"
    assert "--no-session-persistence" in argv
    assert "--permission-mode" not in argv
    assert argv[argv.index("--add-dir") + 1] == str(request.image_path.parent)
    # The prompt is the trailing positional and embeds the image via @-syntax.
    assert argv[-1].endswith(f"@{request.image_path}")
    assert request.system_instruction in argv[-1]
    assert request.prompt_text in argv[-1]


def test_claude_adapter_classifies_timeout(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(exception=subprocess.TimeoutExpired(cmd="claude", timeout=1))
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "timeout"
    assert result.normalized_text == ""


def test_claude_adapter_classifies_missing_binary(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(exception=FileNotFoundError("claude: not found"))
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "claude_binary_missing"


def test_claude_adapter_classifies_login_required(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(returncode=1, stderr="Error: not logged in. Please run `claude auth login`.")
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "login_required"
    assert "not logged in" in (result.error_message or "")


def test_claude_adapter_classifies_process_failure(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(returncode=2, stderr="Error: model claude-mystery not recognized.")
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "process_failure"
    assert "claude-mystery" in (result.error_message or "")


def test_claude_adapter_classifies_empty_output(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    runner = FakeRunner(stdout="")
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=0)

    result = adapter.predict(request)

    assert result.error_type == "empty_output"


def test_claude_adapter_retries_on_transient_failure(tmp_path: Path) -> None:
    request = _build_request(tmp_path)

    class FlakyRunner:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, argv: list[str], **kwargs: Any) -> FakeCompleted:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
            return FakeCompleted(
                returncode=0,
                stdout="filled_square(cx=5, cy=5, size=3)\n",
                stderr="",
            )

    runner = FlakyRunner()
    adapter = ClaudeCodeAdapter(subprocess_run=runner, max_retries=2)

    import ui_bench.adapters.claude_code_adapter as claude_module

    original_sleep = claude_module.time.sleep
    claude_module.time.sleep = lambda _: None
    try:
        result = adapter.predict(request)
    finally:
        claude_module.time.sleep = original_sleep

    assert runner.calls == 2
    assert result.error_type is None
    assert result.normalized_text == "filled_square(cx=5, cy=5, size=3)"


def test_claude_adapter_to_config_is_serializable() -> None:
    adapter = ClaudeCodeAdapter(
        model="claude-opus-4-7[1m]",
        effort="high",
        timeout_seconds=300,
        max_retries=1,
        extra_args=("--debug",),
    )

    config = adapter.to_config()

    assert config == {
        "provider": "claude",
        "model": "claude-opus-4-7[1m]",
        "effort": "high",
        "timeout_seconds": 300,
        "claude_binary": "claude",
        "max_retries": 1,
        "extra_args": ["--debug"],
    }


def test_claude_adapter_rejects_unknown_effort() -> None:
    with pytest.raises(ValueError):
        ClaudeCodeAdapter(effort="ludicrous")


def test_claude_adapter_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError):
        ClaudeCodeAdapter(timeout_seconds=0)


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

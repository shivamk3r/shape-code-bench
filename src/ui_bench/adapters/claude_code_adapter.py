from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from ui_bench.adapters.base import PredictionRequest, PredictionResult
from ui_bench.normalization import normalize_prediction_text

DEFAULT_CLAUDE_MODEL = "claude-opus-4-7[1m]"
DEFAULT_CLAUDE_EFFORT = "medium"
DEFAULT_CLAUDE_TIMEOUT_SECONDS = 240
DEFAULT_CLAUDE_BINARY = "claude"
DEFAULT_CLAUDE_MAX_RETRIES = 2

CLAUDE_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

_LOGIN_ERROR_RE = re.compile(r"\b(not logged in|login required|unauthorized|authentication)\b", re.IGNORECASE)
_RATE_LIMIT_RE = re.compile(r"\b(rate limit|too many requests|429)\b", re.IGNORECASE)


class ClaudeCodeAdapter:
    """Invoke the Claude Code CLI (``claude --print``) via subprocess.

    Uses the user's Claude subscription rather than an API key. The assistant's
    final text is captured from stdout (``--output-format text``) and normalized
    through the shared prediction-text normalizer. The image path is referenced
    inline via Claude Code's ``@<path>`` file syntax, with ``--add-dir`` granting
    read access to the image's parent directory.
    """

    provider = "claude"

    def __init__(
        self,
        *,
        model: str = DEFAULT_CLAUDE_MODEL,
        effort: str = DEFAULT_CLAUDE_EFFORT,
        timeout_seconds: int = DEFAULT_CLAUDE_TIMEOUT_SECONDS,
        claude_binary: str = DEFAULT_CLAUDE_BINARY,
        max_retries: int = DEFAULT_CLAUDE_MAX_RETRIES,
        extra_args: tuple[str, ...] = (),
        subprocess_run: Any = None,
    ) -> None:
        if effort not in CLAUDE_EFFORT_LEVELS:
            allowed = ", ".join(CLAUDE_EFFORT_LEVELS)
            raise ValueError(f"Unsupported effort '{effort}'. Expected one of: {allowed}.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.model = model
        self.effort = effort
        self.timeout_seconds = timeout_seconds
        self.claude_binary = claude_binary
        self.max_retries = max_retries
        self.extra_args = tuple(extra_args)
        self._run = subprocess_run or subprocess.run

    def predict(self, request: PredictionRequest) -> PredictionResult:
        started = time.perf_counter()

        attempts = self.max_retries + 1
        last_error: PredictionResult | None = None
        for attempt in range(1, attempts + 1):
            outcome = self._run_once(request, started)

            if outcome.error_type is None:
                return outcome

            last_error = outcome
            if not _is_transient(outcome.error_type) or attempt == attempts:
                return outcome
            time.sleep(min(30.0, 2.0 * (2 ** (attempt - 1))))

        assert last_error is not None
        return last_error

    def to_config(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "timeout_seconds": self.timeout_seconds,
            "claude_binary": self.claude_binary,
            "max_retries": self.max_retries,
            "extra_args": list(self.extra_args),
        }

    def _run_once(self, request: PredictionRequest, started: float) -> PredictionResult:
        argv = self._build_argv(image_path=request.image_path, request=request)

        try:
            completed = self._run(
                argv,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            return self._error("claude_binary_missing", f"Claude binary not found: {exc}", started)
        except subprocess.TimeoutExpired as exc:
            return self._error("timeout", f"claude --print timed out after {self.timeout_seconds}s: {exc}", started)
        except Exception as exc:
            return self._error("unexpected_adapter_error", str(exc), started)

        returncode = getattr(completed, "returncode", 0)
        stderr = (getattr(completed, "stderr", "") or "")[:500]
        stdout = getattr(completed, "stdout", "") or ""

        if returncode != 0:
            if _LOGIN_ERROR_RE.search(stderr):
                return self._error("login_required", stderr or "claude login required", started)
            if _RATE_LIMIT_RE.search(stderr):
                return self._error("rate_limit_error", stderr or "claude rate-limited", started)
            return self._error("process_failure", stderr or f"claude --print returned {returncode}", started)

        if not stdout.strip():
            return self._error("empty_output", "claude produced no stdout", started)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return PredictionResult(
            raw_text=stdout,
            normalized_text=normalize_prediction_text(stdout),
            model=self.model,
            request_id=None,
            usage=None,
            latency_ms=latency_ms,
            error_type=None,
            error_message=None,
        )

    def _build_argv(self, *, image_path: Path, request: PredictionRequest) -> list[str]:
        prompt_body = (
            f"{request.system_instruction}\n\n{request.prompt_text}\n\n"
            f"Attached image: @{image_path}"
        )
        argv = [
            self.claude_binary,
            "--print",
            "--add-dir",
            str(image_path.parent),
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--output-format",
            "text",
            "--no-session-persistence",
        ]
        argv.extend(self.extra_args)
        argv.append(prompt_body)
        return argv

    def _error(self, error_type: str, message: str, started: float) -> PredictionResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return PredictionResult.from_error(
            model=self.model,
            error_type=error_type,
            error_message=message,
            latency_ms=latency_ms,
        )


def _is_transient(error_type: str) -> bool:
    return error_type in {"timeout", "process_failure", "rate_limit_error"}

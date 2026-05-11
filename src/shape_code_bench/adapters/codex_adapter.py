from __future__ import annotations

import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from shape_code_bench.adapters.base import PredictionRequest, PredictionResult
from shape_code_bench.normalization import normalize_prediction_text

DEFAULT_CODEX_MODEL = "gpt-5.5"
DEFAULT_CODEX_SANDBOX = "read-only"
DEFAULT_CODEX_TIMEOUT_SECONDS = 180
DEFAULT_CODEX_BINARY = "codex"
DEFAULT_CODEX_MAX_RETRIES = 2

_LOGIN_ERROR_RE = re.compile(r"\b(not logged in|login required|unauthorized|authentication)\b", re.IGNORECASE)
_RATE_LIMIT_RE = re.compile(r"\b(rate limit|too many requests|429)\b", re.IGNORECASE)


class CodexAdapter:
    """Invoke the OpenAI Codex CLI (``codex exec``) via subprocess.

    Uses the user's ChatGPT login (e.g. ChatGPT Pro) rather than an API key.
    The agent's final message is captured with ``--output-last-message`` and
    normalized through the shared prediction-text normalizer.
    """

    provider = "codex"

    def __init__(
        self,
        *,
        model: str = DEFAULT_CODEX_MODEL,
        sandbox: str = DEFAULT_CODEX_SANDBOX,
        timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS,
        codex_binary: str = DEFAULT_CODEX_BINARY,
        max_retries: int = DEFAULT_CODEX_MAX_RETRIES,
        reasoning_effort: str | None = None,
        extra_args: tuple[str, ...] = (),
        subprocess_run: Any = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.model = model
        self.sandbox = sandbox
        self.timeout_seconds = timeout_seconds
        self.codex_binary = codex_binary
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self.extra_args = tuple(extra_args)
        self._run = subprocess_run or subprocess.run

    def predict(self, request: PredictionRequest) -> PredictionResult:
        started = time.perf_counter()
        prompt = f"{request.system_instruction}\n\n{request.prompt_text}"

        attempts = self.max_retries + 1
        last_error: PredictionResult | None = None
        for attempt in range(1, attempts + 1):
            outcome = self._run_once(request.image_path, prompt, started)

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
            "sandbox": self.sandbox,
            "timeout_seconds": self.timeout_seconds,
            "codex_binary": self.codex_binary,
            "max_retries": self.max_retries,
            "reasoning_effort": self.reasoning_effort,
            "extra_args": list(self.extra_args),
        }

    def _run_once(self, image_path: Path, prompt: str, started: float) -> PredictionResult:
        with tempfile.TemporaryDirectory(prefix="shape-code-bench-codex-") as workdir:
            output_path = Path(workdir) / "last-message.txt"
            argv = self._build_argv(image_path=image_path, output_path=output_path, workdir=workdir, prompt=prompt)

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
                return self._error("codex_binary_missing", f"Codex binary not found: {exc}", started)
            except subprocess.TimeoutExpired as exc:
                return self._error("timeout", f"codex exec timed out after {self.timeout_seconds}s: {exc}", started)
            except Exception as exc:
                return self._error("unexpected_adapter_error", str(exc), started)

            returncode = getattr(completed, "returncode", 0)
            stderr = (getattr(completed, "stderr", "") or "")[:500]

            if returncode != 0:
                if _LOGIN_ERROR_RE.search(stderr):
                    return self._error("login_required", stderr or "codex login required", started)
                if _RATE_LIMIT_RE.search(stderr):
                    return self._error("rate_limit_error", stderr or "codex rate-limited", started)
                return self._error("process_failure", stderr or f"codex exec returned {returncode}", started)

            if not output_path.exists():
                return self._error("empty_output", "codex did not produce an output file", started)

            raw_text = output_path.read_text(encoding="utf-8")
            if not raw_text.strip():
                return self._error("empty_output", "codex output file was empty", started)

            latency_ms = int((time.perf_counter() - started) * 1000)
            return PredictionResult(
                raw_text=raw_text,
                normalized_text=normalize_prediction_text(raw_text),
                model=self.model,
                request_id=None,
                usage=None,
                latency_ms=latency_ms,
                error_type=None,
                error_message=None,
            )

    def _build_argv(
        self,
        *,
        image_path: Path,
        output_path: Path,
        workdir: str,
        prompt: str,
    ) -> list[str]:
        argv = [
            self.codex_binary,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-s",
            self.sandbox,
            "-m",
            self.model,
            "-i",
            str(image_path),
            "-o",
            str(output_path),
            "-C",
            workdir,
            "--color",
            "never",
        ]
        if self.reasoning_effort is not None:
            argv.extend(["-c", f"reasoning_effort={self.reasoning_effort}"])
        argv.extend(self.extra_args)
        argv.append(prompt)
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

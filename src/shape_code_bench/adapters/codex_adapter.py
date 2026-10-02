from __future__ import annotations

import json
import re
import shutil
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
CODEX_REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "extra_high", "max", "ultra")

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
        if reasoning_effort is not None and reasoning_effort not in CODEX_REASONING_EFFORTS:
            raise ValueError(f"Unsupported Codex reasoning effort: {reasoning_effort}")

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
            if time.perf_counter() - started >= self.timeout_seconds:
                return self._error("timeout", f"Sample exceeded {self.timeout_seconds}s budget", started)
            outcome = self._run_once(request.image_path, prompt, started)

            if outcome.error_type is None:
                return outcome

            last_error = outcome
            if not _is_transient(outcome.error_type) or attempt == attempts:
                return outcome
            remaining = self.timeout_seconds - (time.perf_counter() - started)
            if remaining <= 0:
                return self._error("timeout", f"Sample exceeded {self.timeout_seconds}s budget", started)
            time.sleep(min(remaining, 30.0, 2.0 * (2 ** (attempt - 1))))

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
            "effective_reasoning_effort": self.effective_reasoning_effort,
            "reasoning_effort_config_key": "model_reasoning_effort",
            "timeout_scope": "sample_including_retries",
            "image_isolation": "temporary_png_copy",
            "extra_args": list(self.extra_args),
        }

    @property
    def effective_reasoning_effort(self) -> str | None:
        return "xhigh" if self.reasoning_effort == "extra_high" else self.reasoning_effort

    def runtime_info(self) -> dict[str, str]:
        try:
            completed = subprocess.run(
                [self.codex_binary, "--version"], capture_output=True, text=True, timeout=5,
                check=False,
            )
            return {"codex_version": completed.stdout.strip()}
        except (OSError, subprocess.TimeoutExpired):
            return {"codex_version": "unavailable"}

    def _run_once(self, image_path: Path, prompt: str, started: float) -> PredictionResult:
        with tempfile.TemporaryDirectory(prefix="shape-code-bench-codex-") as workdir:
            isolated_image = Path(workdir) / "input.png"
            shutil.copyfile(image_path.resolve(), isolated_image)
            output_path = Path(workdir) / "last-message.txt"
            argv = self._build_argv(
                image_path=isolated_image, output_path=output_path, workdir=workdir, prompt=prompt,
            )

            try:
                completed = self._run(
                    argv,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    timeout=max(0.001, self.timeout_seconds - (time.perf_counter() - started)),
                    check=False,
                    cwd=workdir,
                )
            except FileNotFoundError as exc:
                return self._error("codex_binary_missing", f"Codex binary not found: {exc}", started)
            except subprocess.TimeoutExpired as exc:
                return self._error("timeout", f"codex exec timed out after {self.timeout_seconds}s: {exc}", started)
            except Exception as exc:
                return self._error("unexpected_adapter_error", str(exc), started)

            returncode = getattr(completed, "returncode", 0)
            stderr = (getattr(completed, "stderr", "") or "")

            if returncode != 0:
                if _LOGIN_ERROR_RE.search(stderr):
                    return self._error("login_required", stderr[-2000:] or "codex login required", started)
                if _RATE_LIMIT_RE.search(stderr):
                    return self._error("rate_limit_error", stderr[-2000:] or "codex rate-limited", started)
                return self._error("process_failure", stderr[-2000:] or f"codex exec returned {returncode}", started)

            if not output_path.exists():
                return self._error("empty_output", "codex did not produce an output file", started)

            raw_text = output_path.read_text(encoding="utf-8")
            if not raw_text.strip():
                return self._error("empty_output", "codex output file was empty", started)

            latency_ms = int((time.perf_counter() - started) * 1000)
            request_id, usage = _event_metadata(getattr(completed, "stdout", "") or "")
            return PredictionResult(
                raw_text=raw_text,
                normalized_text=normalize_prediction_text(raw_text),
                model=self.model,
                request_id=request_id,
                usage=usage,
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
            "--json",
        ]
        if self.reasoning_effort is not None:
            argv.extend(["-c", f"model_reasoning_effort={self.effective_reasoning_effort}"])
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


def _event_metadata(stdout: str) -> tuple[str | None, dict[str, Any] | None]:
    """Keep only reproducibility metadata, never tool logs or reasoning traces."""
    request_id = None
    usage = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "thread.started":
            request_id = event.get("thread_id")
        elif event.get("type") == "turn.completed":
            usage = event.get("usage")
    return request_id, usage

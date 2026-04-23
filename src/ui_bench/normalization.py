from __future__ import annotations

import re

FENCED_ANYWHERE_RE = re.compile(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)\n```", re.DOTALL)
PRIMITIVE_LINE_RE = re.compile(
    r"^\s*(?:filled_circle|circle|filled_square|square)\s*\([^)]*\)\s*$"
)


def normalize_prediction_text(raw_text: str) -> str:
    """Extract DSL code from a free-form model response.

    Strategy (first match wins):
    1. If the output contains a fenced code block anywhere, return its body.
    2. Otherwise, keep only the lines that match a ui-bench primitive signature.
    3. If nothing matches, return the trimmed raw text so that parse errors
       surface honestly in ``error_type_counts`` rather than being papered over.
    """
    text = raw_text.strip()
    if not text:
        return ""

    match = FENCED_ANYWHERE_RE.search(text)
    if match:
        return match.group(1).strip()

    primitive_lines = [line for line in text.splitlines() if PRIMITIVE_LINE_RE.match(line)]
    if primitive_lines:
        return "\n".join(line.strip() for line in primitive_lines)

    return text

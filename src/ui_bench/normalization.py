from __future__ import annotations

import re

FENCED_BLOCK_RE = re.compile(r"\A```(?:[A-Za-z0-9_+.-]+)?\s*\n(?P<body>.*)\n```\Z", re.DOTALL)


def normalize_prediction_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""

    match = FENCED_BLOCK_RE.fullmatch(text)
    if match:
        return match.group("body").strip()

    return text


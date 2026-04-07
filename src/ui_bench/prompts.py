from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSpec:
    mode: str
    system_instruction: str
    user_text: str

    def to_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "system_instruction": self.system_instruction,
            "user_text": self.user_text,
        }


def build_zero_shot_prompt_spec() -> PromptSpec:
    system_instruction = (
        "Return only valid ui-bench DSL code. Do not include markdown fences, comments, or prose."
    )
    user_text = "\n".join(
        [
            "Reconstruct the 512x512 image as ui-bench DSL.",
            "Allowed:",
            "filled_circle(cx=<int>, cy=<int>, radius=<int>)",
            "circle(cx=<int>, cy=<int>, radius=<int>, stroke=<int>)",
            "filled_square(cx=<int>, cy=<int>, size=<int>)",
            "square(cx=<int>, cy=<int>, size=<int>, stroke=<int>)",
            "Use only integers.",
            "Use one function call per line.",
            "Do not output imports, variables, loops, explanations, or markdown.",
        ]
    )
    return PromptSpec(
        mode="zero-shot",
        system_instruction=system_instruction,
        user_text=user_text,
    )

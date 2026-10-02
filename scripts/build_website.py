"""Build the public research website from benchmark and paper sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from shape_code_bench.dsl import parse_program, serialize_scene
from shape_code_bench.evaluator import evaluate_program
from shape_code_bench.generator import DIFFICULTY_SETTINGS, generate_scene
from shape_code_bench.renderer import render_scene
from shape_code_bench.types import CANVAS_SIZE, FUNCTION_NAMES, Scene

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
PAPER_RESULTS = ROOT / "paper/tables/main_results.csv"
SITE_URL = "https://shivamk3r.github.io/shape-code-bench/"
EXAMPLE_SEEDS = {"easy": 101, "medium": 202, "hard": 303}
HERO_PROGRAM = """filled_circle(cx=128, cy=128, radius=64)
square(cx=370, cy=128, size=128, stroke=6)
filled_square(cx=128, cy=370, size=128)
circle(cx=370, cy=370, radius=64, stroke=6)
"""


def load_results() -> list[dict[str, str | float | int]]:
    with PAPER_RESULTS.open(newline="", encoding="utf-8") as handle:
        return [
            {
                key: value
                if key in {"model", "provider", "model_id", "difficulty"}
                else int(value)
                if key == "n"
                else float(value)
                for key, value in row.items()
            }
            for row in csv.DictReader(handle)
        ]


def display_model(row: dict) -> tuple[str, str]:
    if row["provider"] == "codex":
        effort = row["model"].split("(")[-1].rstrip(")")
        return "GPT-5.5", f"{effort} effort · Codex CLI"
    if row["provider"] == "claude":
        effort = row["model"].split("(")[-1].rstrip(")")
        return "Claude Opus 4.7", f"{effort} effort · 1M context · Claude Code"
    if row["provider"] == "heuristic":
        return "Heuristic-CV", "Classical computer vision"
    if row["provider"] == "empty":
        return "Empty-Program", "Parse-failure floor"
    return str(row["model"]), str(row["provider"])


def result_rows(results: list[dict], difficulty: str = "all") -> str:
    rows = sorted(
        (row for row in results if row["difficulty"] == difficulty),
        key=lambda row: row["mean_foreground_iou"],
        reverse=True,
    )
    markup = []
    for row in rows:
        name, description = display_model(row)
        cells = []
        for metric in (
            "exact_match_rate",
            "mean_pixel_accuracy",
            "mean_foreground_iou",
            "parse_success_rate",
        ):
            value = row[metric] * 100
            low = row[f"{metric}_ci_low"] * 100
            high = row[f"{metric}_ci_high"] * 100
            bar = ""
            if metric == "mean_foreground_iou":
                bar = f'<span class="score-bar" style="--score: {value:.4f}%"></span>'
            cells.append(
                f'<td>{bar}<span class="score-value">{value:.1f}%</span>'
                f'<span class="confidence">[{low:.1f}, {high:.1f}]</span></td>'
            )
        markup.append(
            f'<tr><th scope="row">{html.escape(name)}'
            f'<span class="model-detail">{html.escape(description)}</span></th>'
            + "".join(cells)
            + "</tr>"
        )
    return "\n".join(markup)


def build_examples(output: Path) -> dict:
    scenes_dir = output / "assets/scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    examples = {}
    for tier, seed in EXAMPLE_SEEDS.items():
        scene = generate_scene(tier, seed)
        target = render_scene(scene)
        target_path = scenes_dir / f"{tier}-target.png"
        target.save(target_path)
        variants = []
        for shift in range(13):
            first = replace(scene.shapes[0], cx=scene.shapes[0].cx + shift)
            prediction_scene = Scene((first, *scene.shapes[1:]))
            program = serialize_scene(prediction_scene)
            prediction = render_scene(prediction_scene)
            image_path = scenes_dir / f"{tier}-{shift}.png"
            prediction.save(image_path)
            target_pixels = np.asarray(target) == 0
            predicted_pixels = np.asarray(prediction) == 0
            difference = np.full((CANVAS_SIZE, CANVAS_SIZE, 3), 255, dtype=np.uint8)
            difference[target_pixels & predicted_pixels] = (25, 31, 29)
            difference[target_pixels ^ predicted_pixels] = (193, 67, 36)
            diff_path = scenes_dir / f"{tier}-{shift}-diff.png"
            Image.fromarray(difference).save(diff_path)
            variants.append(
                {
                    "shift": shift,
                    "program": program,
                    "image": image_path.relative_to(output).as_posix(),
                    "difference": diff_path.relative_to(output).as_posix(),
                    **evaluate_program(str(target_path), program).to_dict(),
                }
            )
        examples[tier] = {
            "seed": seed,
            "num_shapes": len(scene.shapes),
            "target": target_path.relative_to(output).as_posix(),
            "min_shapes": DIFFICULTY_SETTINGS[tier].min_shapes,
            "max_shapes": DIFFICULTY_SETTINGS[tier].max_shapes,
            "variants": variants,
        }
    return examples


def social_image(output: Path) -> None:
    image = Image.new("RGB", (1200, 630), "#f6f5f0")
    draw = ImageDraw.Draw(image)
    font_path = SOURCE / "assets/fonts/Manrope.ttf"
    title_font = ImageFont.truetype(str(font_path), 69)
    body_font = ImageFont.truetype(str(font_path), 30)
    label_font = ImageFont.truetype(str(font_path), 23)
    title_font.set_variation_by_axes([650])
    body_font.set_variation_by_axes([400])
    label_font.set_variation_by_axes([500])
    draw.rectangle((0, 0, 1200, 12), fill="#c14324")
    draw.text((64, 63), "VISION → CODE → EVALUATION", font=label_font, fill="#c14324")
    draw.text((60, 158), "ShapeCodeBench", font=title_font, fill="#191f1d")
    draw.text((64, 280), "A renewable benchmark for", font=body_font, fill="#4f5652")
    draw.text((64, 326), "perception-to-program reconstruction.", font=body_font, fill="#4f5652")
    draw.text(
        (64, 510),
        f"{len(FUNCTION_NAMES)} primitives. {len(DIFFICULTY_SETTINGS)} difficulty tiers. Fresh seeds.",
        font=label_font,
        fill="#191f1d",
    )
    scene = render_scene(parse_program(HERO_PROGRAM)).convert("RGB").resize((355, 355))
    image.paste(scene, (800, 150))
    draw.rectangle((799, 149, 1156, 506), outline="#d6d9cf", width=2)
    image.save(output / "assets/social-card.png")


def build_website(output: Path) -> None:
    output = output.resolve()
    if output == ROOT or output == SOURCE or output in SOURCE.parents:
        raise ValueError("Choose a build directory separate from the website sources.")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE / "assets", output / "assets", dirs_exist_ok=True)
    # The TTF is only a build input for the social card; the browser uses WOFF2.
    (output / "assets/fonts/Manrope.ttf").unlink()
    for name in ("styles.css", "app.js"):
        shutil.copyfile(SOURCE / name, output / name)
    examples = build_examples(output)
    results = load_results()
    overall = [row for row in results if row["difficulty"] == "all"]
    if not overall or len({row["n"] for row in overall}) != 1:
        raise ValueError("Paper results must use a consistent evaluation sample count.")
    multimodal = [row for row in overall if row["provider"] in {"codex", "claude", "openai"}]
    best_iou = max(multimodal, key=lambda row: row["mean_foreground_iou"])
    best_exact = max(multimodal, key=lambda row: row["exact_match_rate"])
    citation_match = re.search(
        r"```bibtex\n(.*?)\n```",
        (ROOT / "README.md").read_text(encoding="utf-8"),
        re.S,
    )
    if citation_match is None:
        raise ValueError("README.md must include the public BibTeX citation.")
    citation = citation_match.group(1) + "\n"
    (output / "citation.bib").write_text(citation, encoding="utf-8")
    data = {"examples": examples, "results": results}
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":")).replace("<", "\\u003c")
    replacements = {
        "@@BENCHMARK_DATA@@": serialized,
        "@@RESULT_ROWS@@": result_rows(results),
        "@@HERO_PROGRAM@@": html.escape(HERO_PROGRAM.rstrip()),
        "@@INITIAL_PROGRAM@@": html.escape(examples["easy"]["variants"][0]["program"].rstrip()),
        "@@CANVAS_SIZE@@": str(CANVAS_SIZE),
        "@@PRIMITIVE_COUNT@@": str(len(FUNCTION_NAMES)),
        "@@TIER_COUNT@@": str(len(DIFFICULTY_SETTINGS)),
        "@@EVAL_COUNT@@": str(overall[0]["n"]),
        "@@BEST_LLM_IOU@@": f"{best_iou['mean_foreground_iou'] * 100:.1f}",
        "@@BEST_LLM_EXACT@@": f"{best_exact['exact_match_rate'] * 100:.1f}",
        "@@BEST_IOU_NAME@@": html.escape(" · ".join(display_model(best_iou))),
        "@@BEST_EXACT_NAME@@": html.escape(" · ".join(display_model(best_exact))),
        "@@CITATION@@": html.escape(citation.rstrip()),
    }
    markup = (SOURCE / "index.html").read_text(encoding="utf-8")
    for token, replacement in replacements.items():
        markup = markup.replace(token, replacement)
    if "@@" in markup:
        raise ValueError("Unresolved website template token.")
    (output / "index.html").write_text(markup, encoding="utf-8")
    render_scene(parse_program(HERO_PROGRAM)).save(output / "assets/hero-scene.png")
    social_image(output)
    data_dir = output / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "benchmark.json").write_text(serialized + "\n", encoding="utf-8")
    shutil.copyfile(PAPER_RESULTS, data_dir / "main_results.csv")
    (output / ".nojekyll").touch()
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{SITE_URL}</loc></url></urlset>\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/website")
    args = parser.parse_args()
    build_website(args.output_dir)
    print(f"Built research website at {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()

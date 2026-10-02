from __future__ import annotations

import csv
import hashlib
import json
import runpy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
from PIL import Image

from shape_code_bench.dsl import parse_program
from shape_code_bench.evaluator import evaluate_program
from shape_code_bench.generator import generate_scene
from shape_code_bench.renderer import render_scene

ROOT = Path(__file__).resolve().parents[1]
BUILDER = runpy.run_path(str(ROOT / "scripts/build_website.py"))


class WebsiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        for key in ("href", "src"):
            if attributes.get(key):
                self.links.append(attributes[key])


def test_website_build_is_deterministic_and_all_local_links_resolve(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for output in (first, second):
        BUILDER["build_website"](output)
    hashes = [
        {
            path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in output.rglob("*")
            if path.is_file()
        }
        for output in (first, second)
    ]
    assert hashes[0] == hashes[1]
    markup = (first / "index.html").read_text()
    assert "@@" not in markup
    parser = WebsiteParser()
    parser.feed(markup)
    assert len(parser.ids) == len(set(parser.ids))
    for link in parser.links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            continue
        assert not parsed.path.startswith("/"), f"Project Pages needs relative paths: {link}"
        if parsed.path:
            assert (first / unquote(parsed.path)).is_file(), link
        if parsed.fragment:
            assert parsed.fragment in parser.ids, link
    assert (first / "citation.bib").read_text().strip() in (ROOT / "README.md").read_text()
    assert Image.open(first / "assets/social-card.png").size == (1200, 630)
    assert not (first / "assets/fonts/Manrope.ttf").exists()
    assert {path.parts[0] for path in map(Path, hashes[0])} == {
        "assets",
        "data",
        "app.js",
        "styles.css",
        "index.html",
        "citation.bib",
        ".nojekyll",
        "robots.txt",
        "sitemap.xml",
    }


def test_website_scenes_scores_and_every_result_match_their_sources(tmp_path: Path) -> None:
    output = tmp_path / "site"
    BUILDER["build_website"](output)
    data = json.loads((output / "data/benchmark.json").read_text())
    for tier, example in data["examples"].items():
        target_path = output / example["target"]
        assert np.array_equal(
            np.asarray(Image.open(target_path)),
            np.asarray(render_scene(generate_scene(tier, example["seed"]))),
        )
        for variant in example["variants"]:
            assert np.array_equal(
                np.asarray(Image.open(output / variant["image"])),
                np.asarray(render_scene(parse_program(variant["program"]))),
            )
            for metric, value in (
                evaluate_program(str(target_path), variant["program"]).to_dict().items()
            ):
                assert variant[metric] == value
        assert example["variants"][0]["exact_match"] is True
        assert example["variants"][-1]["exact_match"] is False
    with (ROOT / "paper/tables/main_results.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(data["results"]) == len(rows)
    for source, published in zip(rows, data["results"], strict=True):
        for key, value in source.items():
            assert published[key] == (value if isinstance(published[key], str) else float(value))
    assert (output / "data/main_results.csv").read_bytes() == (
        ROOT / "paper/tables/main_results.csv"
    ).read_bytes()
    followup = ROOT / "results/gpt-6.1-sol-max-eval-v1"
    with (followup / "main_results.csv").open(newline="") as handle:
        sol_rows = list(csv.DictReader(handle))
    assert len(data["sol_results"]) == 4
    for source, published in zip(sol_rows, data["sol_results"], strict=True):
        for key, value in source.items():
            assert published[key] == (value if isinstance(published[key], str) else float(value))
    for name in ("main_results.csv", "sample_metrics.csv", "protocol.json", "summary.json"):
        assert (output / f"data/gpt-6.1-sol-max-{name}").read_bytes() == (followup / name).read_bytes()
    markup = (output / "index.html").read_text()
    assert "GPT-6.1 Sol" in markup
    assert "model_reasoning_effort=max" in markup
    assert "HISTORICAL / PAPER V1" in markup
    assert markup.count('id="sol-results-body"') == 1
    assert BUILDER["display_model"](data["sol_results"][0])[0] == "GPT-6.1 Sol"


def test_followup_aggregates_and_protocol_match_per_sample_metrics() -> None:
    source = ROOT / "results/gpt-6.1-sol-max-eval-v1"
    with (source / "sample_metrics.csv").open(newline="") as handle:
        samples = list(csv.DictReader(handle))
    with (source / "main_results.csv").open(newline="") as handle:
        aggregates = list(csv.DictReader(handle))
    protocol = json.loads((source / "protocol.json").read_text())
    assert len(samples) == 150
    assert len({row["sample_id"] for row in samples}) == 150
    assert protocol["adapter"]["model"] == "gpt-6.1-sol"
    assert protocol["adapter"]["effective_reasoning_effort"] == "max"
    assert protocol["adapter"]["timeout_seconds"] == 3600
    assert protocol["adapter"]["extra_args"] == ["--ignore-user-config"]
    assert protocol["invocations"][0]["new_samples"] == 2
    assert protocol["invocations"][1]["workers"] == 8
    assert protocol["invocations"][1]["new_samples"] == 148
    assert protocol["invocations"][1]["reused_samples"] == 2
    for row in aggregates:
        selected = [sample for sample in samples
                    if row["difficulty"] == "all" or sample["difficulty"] == row["difficulty"]]
        assert len(selected) == int(row["n"])
        assert len(selected) == (150 if row["difficulty"] == "all" else 50)
        for metric, sample_key in {
            "exact_match_rate": "exact_match", "mean_pixel_accuracy": "pixel_accuracy",
            "mean_foreground_iou": "foreground_iou", "parse_success_rate": "parse_success",
        }.items():
            values = [float(sample[sample_key] == "True") if sample_key in {"exact_match", "parse_success"}
                      else float(sample[sample_key]) for sample in selected]
            assert abs(float(row[metric]) - sum(values) / len(values)) < 1e-12
            assert 0 <= float(row[f"{metric}_ci_low"]) <= float(row[f"{metric}_ci_high"]) <= 1

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

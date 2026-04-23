from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ui_bench.adapters.base import PredictionRequest
from ui_bench.baselines import EmptyProgramAdapter, HeuristicCVAdapter
from ui_bench.dsl import parse_program
from ui_bench.evaluator import evaluate_program
from ui_bench.generator import write_generated_sample


def test_empty_adapter_returns_empty_program(tmp_path: Path) -> None:
    request = _build_request(tmp_path)
    adapter = EmptyProgramAdapter()

    result = adapter.predict(request)

    assert result.error_type is None
    assert result.raw_text == ""
    assert result.normalized_text == ""
    assert result.model == "empty-program"


def test_heuristic_recovers_single_filled_square(tmp_path: Path) -> None:
    image_path = tmp_path / "square.png"
    img = Image.new("L", (512, 512), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 100, 199, 199), fill=0)
    img.save(image_path)

    request = PredictionRequest(
        sample_id="synthetic-square",
        image_path=image_path,
        system_instruction="",
        prompt_text="",
    )
    adapter = HeuristicCVAdapter()

    result = adapter.predict(request)

    assert result.error_type is None
    scene = parse_program(result.normalized_text)
    assert len(scene.shapes) == 1
    shape = scene.shapes[0]
    assert type(shape).__name__ == "FilledSquare"


def test_heuristic_recovers_single_filled_circle(tmp_path: Path) -> None:
    image_path = tmp_path / "circle.png"
    img = Image.new("L", (512, 512), color=255)
    draw = ImageDraw.Draw(img)
    draw.ellipse((150, 150, 250, 250), fill=0)
    img.save(image_path)

    request = PredictionRequest(
        sample_id="synthetic-circle",
        image_path=image_path,
        system_instruction="",
        prompt_text="",
    )
    adapter = HeuristicCVAdapter()

    result = adapter.predict(request)

    assert result.error_type is None
    scene = parse_program(result.normalized_text)
    assert len(scene.shapes) == 1
    shape = scene.shapes[0]
    assert type(shape).__name__ == "FilledCircle"


def test_heuristic_returns_parseable_program_on_generated_sample(tmp_path: Path) -> None:
    generated = write_generated_sample(
        split="train",
        difficulty="easy",
        seed=7,
        output_dir=str(tmp_path / "generated"),
    )
    request = PredictionRequest(
        sample_id=generated["sample_id"],
        image_path=Path(generated["image_path"]),
        system_instruction="",
        prompt_text="",
    )
    adapter = HeuristicCVAdapter()

    result = adapter.predict(request)

    assert result.error_type is None
    evaluation = evaluate_program(generated["image_path"], result.normalized_text)
    assert evaluation.parse_success
    assert evaluation.execution_success


def test_heuristic_handles_empty_image(tmp_path: Path) -> None:
    image_path = tmp_path / "empty.png"
    Image.new("L", (512, 512), color=255).save(image_path)
    request = PredictionRequest(
        sample_id="empty-image",
        image_path=image_path,
        system_instruction="",
        prompt_text="",
    )
    adapter = HeuristicCVAdapter()

    result = adapter.predict(request)

    assert result.error_type is None
    assert result.normalized_text == ""


def test_heuristic_to_config_is_serializable() -> None:
    adapter = HeuristicCVAdapter()
    config = adapter.to_config()
    assert config["provider"] == "heuristic"
    assert "threshold" in config


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
        system_instruction="",
        prompt_text="",
    )

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ui_bench.dsl import DSLValidationError, parse_program, serialize_scene
from ui_bench.evaluator import evaluate_program
from ui_bench.generator import build_sample_metadata, generate_scene, sample_id
from ui_bench.renderer import render_scene


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except DSLValidationError as exc:
        print(json.dumps({"error_type": exc.error_type, "message": str(exc)}, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"error_type": "cli_error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ui-bench benchmark utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate benchmark samples.")
    generate_parser.add_argument("--split", default="train")
    generate_parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), required=True)
    generate_parser.add_argument("--count", type=int, default=1)
    generate_parser.add_argument("--seed", type=int, default=0)
    generate_parser.add_argument("--output-dir", default="data/generated")
    generate_parser.set_defaults(handler=_handle_generate)

    render_parser = subparsers.add_parser("render", help="Render a DSL program to a PNG image.")
    render_parser.add_argument("--program-file", required=True)
    render_parser.add_argument("--output-file", required=True)
    render_parser.set_defaults(handler=_handle_render)

    eval_parser = subparsers.add_parser("eval", help="Evaluate a predicted program against a target image.")
    eval_parser.add_argument("--target-image", required=True)
    eval_parser.add_argument("--prediction-file", required=True)
    eval_parser.add_argument("--output-file")
    eval_parser.set_defaults(handler=_handle_eval)

    return parser


def _handle_generate(args: argparse.Namespace) -> int:
    if args.count < 1:
        raise ValueError("--count must be at least 1.")

    output_root = Path(args.output_dir) / args.split / args.difficulty
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for offset in range(args.count):
        current_seed = args.seed + offset
        scene = generate_scene(args.difficulty, current_seed)
        program = serialize_scene(scene)
        image = render_scene(scene)
        current_sample_id = sample_id(args.split, args.difficulty, current_seed)

        image_path = output_root / f"{current_sample_id}.png"
        metadata_path = output_root / f"{current_sample_id}.json"

        image.save(image_path)
        metadata = build_sample_metadata(args.split, args.difficulty, current_seed, scene, program)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        results.append(
            {
                "sample_id": current_sample_id,
                "image_path": str(image_path),
                "metadata_path": str(metadata_path),
            }
        )

    print(json.dumps({"generated": results}, indent=2))
    return 0


def _handle_render(args: argparse.Namespace) -> int:
    program_text = Path(args.program_file).read_text(encoding="utf-8")
    scene = parse_program(program_text)
    image = render_scene(scene)

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)

    print(
        json.dumps(
            {
                "output_file": str(output_path),
                "num_shapes": len(scene.shapes),
                "canonical_program": serialize_scene(scene),
            },
            indent=2,
        )
    )
    return 0


def _handle_eval(args: argparse.Namespace) -> int:
    prediction_text = Path(args.prediction_file).read_text(encoding="utf-8")
    result = evaluate_program(args.target_image, prediction_text)
    payload = result.to_dict()

    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

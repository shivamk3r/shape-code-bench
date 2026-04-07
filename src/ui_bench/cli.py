from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ui_bench.adapters import (
    DEFAULT_IMAGE_DETAIL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    OpenAIResponsesAdapter,
)
from ui_bench.dsl import DSLValidationError, parse_program, serialize_scene
from ui_bench.evaluator import evaluate_program
from ui_bench.generator import write_generated_sample
from ui_bench.renderer import render_scene
from ui_bench.runner import run_benchmark


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

    run_parser = subparsers.add_parser("run", help="Run a model adapter on a generated dataset.")
    run_parser.add_argument("--dataset-dir", required=True)
    run_parser.add_argument("--provider", choices=("openai",), required=True)
    run_parser.add_argument("--model", default=DEFAULT_OPENAI_MODEL)
    run_parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default=DEFAULT_REASONING_EFFORT,
    )
    run_parser.add_argument(
        "--image-detail",
        choices=("low", "high", "auto", "original"),
        default=DEFAULT_IMAGE_DETAIL,
    )
    run_parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--output-dir", default="data/runs")
    run_parser.set_defaults(handler=_handle_run)

    return parser


def _handle_generate(args: argparse.Namespace) -> int:
    if args.count < 1:
        raise ValueError("--count must be at least 1.")

    results: list[dict[str, object]] = []
    for offset in range(args.count):
        current_seed = args.seed + offset
        results.append(
            write_generated_sample(
                split=args.split,
                difficulty=args.difficulty,
                seed=current_seed,
                output_dir=args.output_dir,
            )
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


def _handle_run(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1 when provided.")

    adapter = _build_adapter_from_args(args)
    result = run_benchmark(
        dataset_dir=args.dataset_dir,
        adapter=adapter,
        limit=args.limit,
        output_dir=args.output_dir,
    )
    payload = {
        "run_id": result.run_id,
        "output_dir": str(result.output_dir),
        "run_config_path": str(result.run_config_path),
        "summary_path": str(result.summary_path),
        "summary": result.summary,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _build_adapter_from_args(args: argparse.Namespace) -> OpenAIResponsesAdapter:
    if args.provider != "openai":
        raise ValueError(f"Unsupported provider '{args.provider}'.")

    return OpenAIResponsesAdapter(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        image_detail=args.image_detail,
        max_output_tokens=args.max_output_tokens,
    )


if __name__ == "__main__":
    raise SystemExit(main())

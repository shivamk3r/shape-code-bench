"""Generate PDF figures for the ui-bench paper.

Inputs:
- ``data/runs/*/summary.json`` and per-sample JSON
- Optional: ``data/eval_v1/`` (for target images) and ``src/ui_bench`` (to render predictions)

Outputs (under ``paper/figures/``):
- ``fig_accuracy_by_difficulty.pdf`` — grouped bar chart with bootstrap 95% CIs
- ``fig_metric_comparison.pdf`` — 2x2 panel of metric comparisons
- ``fig_error_histogram.pdf`` — stacked error-type bars per model
- ``fig_qualitative_grid.pdf`` — target / prediction / diff rows for wins and losses
- ``fig_sample_grid.pdf`` — 3x3 panel of eval_v1 examples per difficulty
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from ui_bench.dsl import DSLValidationError, parse_program
from ui_bench.renderer import render_scene

METRICS = ("exact_match_rate", "mean_pixel_accuracy", "mean_foreground_iou", "parse_success_rate")
METRIC_LABELS = {
    "exact_match_rate": "Exact match",
    "mean_pixel_accuracy": "Pixel accuracy",
    "mean_foreground_iou": "Foreground IoU",
    "parse_success_rate": "Parse success",
}
SAMPLE_METRIC_KEY = {
    "exact_match_rate": "exact_match",
    "mean_pixel_accuracy": "pixel_accuracy",
    "mean_foreground_iou": "foreground_iou",
    "parse_success_rate": "parse_success",
}
DIFFICULTIES = ("easy", "medium", "hard")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render ui-bench paper figures.")
    parser.add_argument("--runs-dir", default="data/runs")
    parser.add_argument("--dataset-dir", default="data/eval_v1")
    parser.add_argument("--output-dir", default="paper/figures")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--qualitative-model",
        default=None,
        help="Run label to use for the qualitative grid (default: best exact_match run).",
    )
    args = parser.parse_args()

    runs = _load_runs(Path(args.runs_dir))
    if not runs:
        raise SystemExit(f"No runs found under {args.runs_dir}.")

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)

    _plot_accuracy_by_difficulty(
        runs=runs,
        output=output_root / "fig_accuracy_by_difficulty.pdf",
        bootstrap=args.bootstrap,
        rng=rng,
    )
    _plot_metric_panel(
        runs=runs,
        output=output_root / "fig_metric_comparison.pdf",
        bootstrap=args.bootstrap,
        rng=rng,
    )
    _plot_error_histogram(
        runs=runs,
        output=output_root / "fig_error_histogram.pdf",
    )

    qualitative_run = _pick_qualitative_run(runs, args.qualitative_model)
    if qualitative_run is not None:
        _plot_qualitative_grid(
            run=qualitative_run,
            output=output_root / "fig_qualitative_grid.pdf",
        )

    _plot_sample_grid(
        dataset_dir=Path(args.dataset_dir),
        output=output_root / "fig_sample_grid.pdf",
    )

    print(json.dumps({"output_dir": str(output_root.resolve())}, indent=2))
    return 0


def _load_runs(runs_root: Path) -> list[dict]:
    runs: list[dict] = []
    for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        samples = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((run_dir / "samples").glob("*.json"))
        ]
        adapter_config: dict = {}
        run_config_path = run_dir / "run_config.json"
        if run_config_path.exists():
            run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
            adapter_config = run_config.get("adapter", {}) or {}
        runs.append(
            {
                "run_dir": run_dir,
                "summary": summary,
                "samples": samples,
                "adapter_config": adapter_config,
                "label": _run_label(summary, adapter_config),
                "provider": summary["provider"],
                "model": summary["model"],
            }
        )
    return runs


def _run_label(summary: dict, adapter_config: dict | None = None) -> str:
    provider = summary["provider"]
    model = summary["model"]
    cfg = adapter_config or {}
    if provider == "heuristic":
        return "Heuristic-CV"
    if provider == "empty":
        return "Empty-Program"
    if provider == "claude":
        effort = cfg.get("effort")
        return f"{model} ({effort})" if effort else model
    if provider == "codex":
        effort = cfg.get("reasoning_effort")
        return f"{model} ({effort})" if effort else model
    if provider == "openai":
        effort = cfg.get("reasoning_effort")
        return f"{model} ({effort})" if effort else model
    return f"{provider}:{model}"


def _metric_values(samples: list[dict], metric: str) -> np.ndarray:
    key = SAMPLE_METRIC_KEY[metric]
    return np.asarray(
        [float(bool(p["evaluation"][key])) if isinstance(p["evaluation"][key], bool) else float(p["evaluation"][key])
         for p in samples],
        dtype=float,
    )


def _bootstrap_ci(values: np.ndarray, *, bootstrap: int, rng: np.random.Generator) -> tuple[float, float]:
    if values.size == 0:
        return (float("nan"), float("nan"))
    idx = rng.integers(0, values.size, size=(bootstrap, values.size))
    means = values[idx].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _plot_accuracy_by_difficulty(
    *,
    runs: list[dict],
    output: Path,
    bootstrap: int,
    rng: np.random.Generator,
) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    n_models = len(runs)
    width = 0.8 / max(1, n_models)

    for i, run in enumerate(runs):
        means: list[float] = []
        low_err: list[float] = []
        high_err: list[float] = []
        for difficulty in DIFFICULTIES:
            subset = [p for p in run["samples"] if p["difficulty"] == difficulty]
            vals = _metric_values(subset, "exact_match_rate")
            mean = float(vals.mean()) if vals.size else 0.0
            lo, hi = _bootstrap_ci(vals, bootstrap=bootstrap, rng=rng)
            means.append(mean)
            low_err.append(max(0.0, mean - lo))
            high_err.append(max(0.0, hi - mean))

        x = np.arange(len(DIFFICULTIES)) + (i - (n_models - 1) / 2) * width
        ax.bar(
            x,
            means,
            width=width,
            label=run["label"],
            yerr=[low_err, high_err],
            capsize=3,
            edgecolor="black",
            linewidth=0.4,
        )

    ax.set_xticks(np.arange(len(DIFFICULTIES)))
    ax.set_xticklabels([d.capitalize() for d in DIFFICULTIES])
    ax.set_ylabel("Exact match rate")
    ax.set_title("Exact match by difficulty (95% bootstrap CI)")
    ax.set_ylim(0.0, 1.0)
    ax.legend(loc="best", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def _plot_metric_panel(
    *,
    runs: list[dict],
    output: Path,
    bootstrap: int,
    rng: np.random.Generator,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.2), sharex=False)
    axes = axes.ravel()
    n_models = len(runs)
    width = 0.8 / max(1, n_models)

    for ax, metric in zip(axes, METRICS):
        for i, run in enumerate(runs):
            means: list[float] = []
            low_err: list[float] = []
            high_err: list[float] = []
            for difficulty in DIFFICULTIES:
                subset = [p for p in run["samples"] if p["difficulty"] == difficulty]
                vals = _metric_values(subset, metric)
                mean = float(vals.mean()) if vals.size else 0.0
                lo, hi = _bootstrap_ci(vals, bootstrap=bootstrap, rng=rng)
                means.append(mean)
                low_err.append(max(0.0, mean - lo))
                high_err.append(max(0.0, hi - mean))

            x = np.arange(len(DIFFICULTIES)) + (i - (n_models - 1) / 2) * width
            ax.bar(
                x,
                means,
                width=width,
                label=run["label"],
                yerr=[low_err, high_err],
                capsize=2,
                edgecolor="black",
                linewidth=0.3,
            )

        ax.set_xticks(np.arange(len(DIFFICULTIES)))
        ax.set_xticklabels([d.capitalize() for d in DIFFICULTIES])
        ax.set_ylim(0.0, 1.0)
        ax.set_title(METRIC_LABELS[metric])

    axes[0].legend(loc="best", frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def _plot_error_histogram(*, runs: list[dict], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.0))

    error_types: list[str] = []
    seen: set[str] = set()
    per_run_counts: list[Counter[str]] = []
    for run in runs:
        counter: Counter[str] = Counter()
        for payload in run["samples"]:
            err = payload["evaluation"].get("error_type") or "none"
            counter[err] += 1
            if err not in seen:
                seen.add(err)
                error_types.append(err)
        per_run_counts.append(counter)

    # Sort error types: "none" last, then alphabetic
    error_types.sort(key=lambda e: (e == "none", e))
    x = np.arange(len(runs))
    bottoms = np.zeros(len(runs), dtype=float)

    colormap = plt.get_cmap("tab20")
    for i, error_type in enumerate(error_types):
        heights = np.asarray([counter.get(error_type, 0) for counter in per_run_counts], dtype=float)
        ax.bar(
            x,
            heights,
            bottom=bottoms,
            label=error_type,
            color=colormap(i % 20),
            edgecolor="black",
            linewidth=0.3,
        )
        bottoms += heights

    ax.set_xticks(x)
    ax.set_xticklabels([run["label"] for run in runs], rotation=20, ha="right")
    ax.set_ylabel("Sample count")
    ax.set_title("Evaluation error taxonomy")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _pick_qualitative_run(runs: list[dict], explicit: str | None) -> dict | None:
    if explicit is not None:
        for run in runs:
            if run["label"] == explicit:
                return run
        return None

    real_model_runs = [r for r in runs if r["provider"] not in ("heuristic", "empty")]
    candidates = real_model_runs or runs
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["summary"]["exact_match_rate"])


def _plot_qualitative_grid(*, run: dict, output: Path) -> None:
    wins: list[dict] = []
    losses: list[dict] = []
    for payload in run["samples"]:
        evaluation = payload["evaluation"]
        if evaluation["exact_match"]:
            wins.append(payload)
        elif evaluation["parse_success"] and evaluation["execution_success"]:
            losses.append(payload)

    wins.sort(key=lambda p: (p["difficulty"], p["sample_id"]))
    losses.sort(key=lambda p: -float(p["evaluation"]["foreground_iou"]))

    k = 3
    wins = wins[:k]
    losses = losses[:k]
    rows = len(wins) + len(losses)
    if rows == 0:
        Image.new("L", (1, 1), 255).save(output)
        return

    fig, axes = plt.subplots(rows, 3, figsize=(7.5, 1.2 * rows), squeeze=False)
    last_win_row = len(wins) - 1
    for row_idx, payload in enumerate(wins + losses):
        target_img = _open_target(payload)
        pred_img = _render_prediction(payload)
        diff_img = _diff_image(target_img, pred_img) if pred_img is not None else None

        axes[row_idx, 0].imshow(target_img, cmap="gray", vmin=0, vmax=255)
        axes[row_idx, 0].set_title(_short_title(payload, kind="target"), fontsize=8)

        if pred_img is not None:
            axes[row_idx, 1].imshow(pred_img, cmap="gray", vmin=0, vmax=255)
        axes[row_idx, 1].set_title(_short_title(payload, kind="prediction"), fontsize=8)

        if diff_img is not None:
            axes[row_idx, 2].imshow(diff_img, cmap="gray", vmin=0, vmax=255)
        axes[row_idx, 2].set_title("XOR diff", fontsize=8)

        for col_idx in range(3):
            _style_qualitative_cell(
                axes[row_idx, col_idx],
                col_idx=col_idx,
                row_idx=row_idx,
                last_row=rows - 1,
                last_win_row=last_win_row,
            )

    fig.suptitle(f"{run['label']} — wins (top {len(wins)}) and losses (bottom {len(losses)})", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _style_qualitative_cell(ax, *, col_idx: int, row_idx: int, last_row: int, last_win_row: int) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("0.6")
        spine.set_linewidth(0.5)

    if col_idx < 2:
        ax.spines["right"].set_edgecolor("0.2")
        ax.spines["right"].set_linewidth(1.0)
    if col_idx > 0:
        ax.spines["left"].set_edgecolor("0.2")
        ax.spines["left"].set_linewidth(1.0)

    if row_idx < last_row:
        is_wins_losses_divider = last_win_row >= 0 and row_idx == last_win_row
        ax.spines["bottom"].set_edgecolor("black" if is_wins_losses_divider else "0.2")
        ax.spines["bottom"].set_linewidth(1.4 if is_wins_losses_divider else 1.0)
    if row_idx > 0:
        is_below_wins_losses_divider = last_win_row >= 0 and row_idx == last_win_row + 1
        ax.spines["top"].set_edgecolor("black" if is_below_wins_losses_divider else "0.2")
        ax.spines["top"].set_linewidth(1.4 if is_below_wins_losses_divider else 1.0)


def _open_target(payload: dict) -> np.ndarray:
    path = Path(payload["image_path"])
    return np.asarray(Image.open(path).convert("L"), dtype=np.uint8)


def _render_prediction(payload: dict) -> np.ndarray | None:
    text = payload["prediction"]["normalized_text"]
    if not text.strip():
        return None
    try:
        scene = parse_program(text)
    except DSLValidationError:
        return None
    try:
        return np.asarray(render_scene(scene).convert("L"), dtype=np.uint8)
    except Exception:
        return None


def _diff_image(target: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    target_fg = target == 0
    pred_fg = prediction == 0
    xor = np.logical_xor(target_fg, pred_fg)
    return np.where(xor, 0, 255).astype(np.uint8)


def _short_title(payload: dict, *, kind: str) -> str:
    difficulty = payload["difficulty"]
    iou = payload["evaluation"]["foreground_iou"]
    sample_id = payload["sample_id"].rsplit("-", 1)[-1]
    if kind == "target":
        return f"{difficulty} #{sample_id}"
    return f"pred IoU={iou:.2f}"


def _plot_sample_grid(*, dataset_dir: Path, output: Path) -> None:
    eval_root = dataset_dir / "eval"
    if not eval_root.exists():
        return

    fig, axes = plt.subplots(3, 3, figsize=(6.4, 6.4))
    for row, difficulty in enumerate(DIFFICULTIES):
        tier_dir = eval_root / difficulty
        images = sorted(tier_dir.glob("*.png"))[:3]
        for col in range(3):
            ax = axes[row, col]
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor("0.6")
                spine.set_linewidth(0.5)
            if col >= len(images):
                continue
            image = np.asarray(Image.open(images[col]).convert("L"), dtype=np.uint8)
            ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            if col == 0:
                ax.set_ylabel(difficulty.capitalize(), fontsize=10)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())

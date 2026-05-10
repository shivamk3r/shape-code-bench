"""Aggregate ui-bench run artifacts into CSV and LaTeX tables.

Walks ``data/runs/*/summary.json``, cross-references per-sample JSON for
bootstrap CIs, and writes ``paper/tables/{main_results.csv, main_results.tex,
error_taxonomy.tex}``.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = ("exact_match_rate", "mean_pixel_accuracy", "mean_foreground_iou", "parse_success_rate")
METRIC_LABELS = {
    "exact_match_rate": "Exact",
    "mean_pixel_accuracy": "PixAcc",
    "mean_foreground_iou": "FG-IoU",
    "parse_success_rate": "Parse",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze ui-bench runs into paper tables.")
    parser.add_argument("--runs-dir", default="data/runs")
    parser.add_argument("--output-dir", default="paper/tables")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    runs_root = Path(args.runs_dir)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runs = _load_runs(runs_root)
    if not runs:
        raise SystemExit(f"No runs found under {runs_root}.")

    main_df = _build_main_df(runs, bootstrap=args.bootstrap_samples, seed=args.seed)
    main_df.to_csv(output_root / "main_results.csv", index=False)
    (output_root / "main_results.tex").write_text(_main_latex(main_df), encoding="utf-8")

    error_df = _build_error_df(runs)
    error_df.to_csv(output_root / "error_taxonomy.csv", index=False)
    (output_root / "error_taxonomy.tex").write_text(_error_latex(error_df), encoding="utf-8")

    print(
        json.dumps(
            {
                "runs": [run["model_label"] for run in runs],
                "main_csv": str((output_root / "main_results.csv").resolve()),
                "error_csv": str((output_root / "error_taxonomy.csv").resolve()),
            },
            indent=2,
        )
    )
    return 0


def _load_runs(runs_root: Path) -> list[dict]:
    runs: list[dict] = []
    for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        samples_dir = run_dir / "samples"
        sample_payloads = []
        for sample_path in sorted(samples_dir.glob("*.json")):
            sample_payloads.append(json.loads(sample_path.read_text(encoding="utf-8")))
        adapter_config: dict = {}
        run_config_path = run_dir / "run_config.json"
        if run_config_path.exists():
            run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
            adapter_config = run_config.get("adapter", {}) or {}
        runs.append(
            {
                "run_dir": run_dir,
                "summary": summary,
                "samples": sample_payloads,
                "adapter_config": adapter_config,
                "model_label": _model_label(summary, adapter_config),
                "provider": summary["provider"],
                "model": summary["model"],
            }
        )
    return runs


def _model_label(summary: dict, adapter_config: dict | None = None) -> str:
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


def _build_main_df(runs: list[dict], *, bootstrap: int, seed: int) -> pd.DataFrame:
    rows: list[dict] = []
    rng = np.random.default_rng(seed)

    for run in runs:
        all_samples = run["samples"]
        by_diff = {"easy": [], "medium": [], "hard": []}
        for payload in all_samples:
            by_diff.setdefault(payload["difficulty"], []).append(payload)

        # Overall row
        rows.append(_row(run=run, difficulty="all", samples=all_samples, bootstrap=bootstrap, rng=rng))
        for difficulty in ("easy", "medium", "hard"):
            rows.append(
                _row(
                    run=run,
                    difficulty=difficulty,
                    samples=by_diff.get(difficulty, []),
                    bootstrap=bootstrap,
                    rng=rng,
                )
            )

    return pd.DataFrame(rows)


def _row(
    *,
    run: dict,
    difficulty: str,
    samples: list[dict],
    bootstrap: int,
    rng: np.random.Generator,
) -> dict:
    n = len(samples)
    row: dict[str, object] = {
        "model": run["model_label"],
        "provider": run["provider"],
        "model_id": run["model"],
        "difficulty": difficulty,
        "n": n,
    }
    if n == 0:
        for metric in METRICS:
            row[metric] = float("nan")
            row[f"{metric}_ci_low"] = float("nan")
            row[f"{metric}_ci_high"] = float("nan")
        return row

    per_sample = {metric: _metric_values(metric, samples) for metric in METRICS}
    for metric, values in per_sample.items():
        row[metric] = float(np.mean(values))
        low, high = _bootstrap_ci(np.asarray(values, dtype=float), bootstrap=bootstrap, rng=rng)
        row[f"{metric}_ci_low"] = float(low)
        row[f"{metric}_ci_high"] = float(high)
    return row


def _metric_values(metric: str, samples: list[dict]) -> list[float]:
    key = _sample_key(metric)
    return [_as_float(payload["evaluation"][key]) for payload in samples]


def _sample_key(metric: str) -> str:
    mapping = {
        "exact_match_rate": "exact_match",
        "mean_pixel_accuracy": "pixel_accuracy",
        "mean_foreground_iou": "foreground_iou",
        "parse_success_rate": "parse_success",
    }
    return mapping[metric]


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)  # type: ignore[arg-type]


def _bootstrap_ci(values: np.ndarray, *, bootstrap: int, rng: np.random.Generator) -> tuple[float, float]:
    if values.size == 0:
        return (float("nan"), float("nan"))
    indices = rng.integers(0, values.size, size=(bootstrap, values.size))
    sample_means = values[indices].mean(axis=1)
    low = float(np.quantile(sample_means, 0.025))
    high = float(np.quantile(sample_means, 0.975))
    return (low, high)


def _build_error_df(runs: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for run in runs:
        counter: Counter[str] = Counter()
        for payload in run["samples"]:
            error_type = payload["evaluation"].get("error_type") or "none"
            counter[error_type] += 1
        for error_type, count in counter.items():
            rows.append(
                {
                    "model": run["model_label"],
                    "provider": run["provider"],
                    "error_type": error_type,
                    "count": count,
                    "n": len(run["samples"]),
                }
            )
    return pd.DataFrame(rows)


def _main_latex(df: pd.DataFrame) -> str:
    overall = df[df["difficulty"] == "all"].copy()
    overall = overall.sort_values("exact_match_rate", ascending=False)

    lines = [
        r"% Auto-generated by scripts/analyze.py. Do not edit by hand.",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Model & " + " & ".join(METRIC_LABELS[m] for m in METRICS) + r" \\",
        r"\midrule",
    ]
    for _, row in overall.iterrows():
        cells = [_escape_latex(str(row["model"]))]
        for metric in METRICS:
            mean = row[metric]
            low = row[f"{metric}_ci_low"]
            high = row[f"{metric}_ci_high"]
            cells.append(f"{mean:.3f} {{\\scriptsize [{low:.3f}, {high:.3f}]}}")
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def _error_latex(df: pd.DataFrame) -> str:
    if df.empty:
        return "% No error rows.\n"

    pivot = df.pivot_table(
        index="error_type",
        columns="model",
        values="count",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()

    columns = list(pivot.columns)
    lines = [
        r"% Auto-generated by scripts/analyze.py. Do not edit by hand.",
        r"\begin{tabular}{l" + "r" * len(columns) + "}",
        r"\toprule",
        r"Error type & " + " & ".join(_escape_latex(str(c)) for c in columns) + r" \\",
        r"\midrule",
    ]
    for error_type, row in pivot.iterrows():
        cells = [_escape_latex(str(error_type))] + [str(int(v)) for v in row.values]
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = []
    for ch in text:
        out.append(replacements.get(ch, ch))
    return "".join(out)


if __name__ == "__main__":
    raise SystemExit(main())

# Continue on other laptop — ui-bench arXiv push

Handoff at **2026-04-24 07:53 local (IST)** after the full `gpt-5.4-mini`
sweep completed and `paper/main.pdf` was rebuilt. All state is on
`wip-transfer-2026-04-23` at commit `7fbf7a3` (pushed to
`git@github.com:shivamiitgoa/ui-bench.git`).

Read this file end-to-end before doing anything.

## 1. Who and what

- User: Shivam Kumar (shivamnexus.sk@gmail.com). Independent ML researcher.
  Python 3.12 + uv; deep Python/ML background; cost-sensitive on API tokens;
  rigorous methodology (frozen seeds, render-based scoring, full artifact
  capture). Prefers terse collaboration.
- Project: `ui-bench` = synthetic perception-to-program benchmark. Four DSL
  primitives (`filled_circle`, `circle`, `filled_square`, `square`), three
  difficulty tiers, 150 samples in `eval_v1`.
- **LLM eval goes through Codex CLI (`codex exec`) + ChatGPT Pro login, NEVER
  the OpenAI API.** The `ModelAdapter` Protocol in
  `src/ui_bench/adapters/base.py` makes providers swappable, but only the
  Codex adapter is used for paper numbers.
- Branch: `wip-transfer-2026-04-23` (throwaway). Do not merge to `main`.

## 2. Environment setup on the new laptop

```bash
pwd                                # should end in /ui-bench
command -v uv >/dev/null || brew install uv
uv sync
uv run pytest -q                   # expect 54 passed, 2 skipped

# Codex CLI — PIN to stable 0.122.0. Do NOT use 0.123.0, alpha, or npm latest.
# The Codex desktop app bundles an alpha pre-release; avoid that too.
npm install -g @openai/codex@0.122.0
which codex && codex --version     # must say exactly 0.122.0
codex login status                 # "Logged in using ChatGPT"

# Paper build deps (for pdflatex + bibtex):
brew install --cask basictex       # requires sudo; restart terminal after
# or: eval "$(/usr/libexec/path_helper)"
/Library/TeX/texbin/pdflatex --version
```

macOS registers `/etc/paths.d/TeX` automatically, so login shells
(`zsh -l`) pick up `/Library/TeX/texbin` without editing any profile.
When invoking the paper Makefile, use `/bin/zsh -lc 'cd paper && make'`
to ensure the PATH is loaded.

## 3. Current sweep state

All 5 runs complete with `summary.json`:

| Run dir | Model | Codex CLI |
|---|---|---|
| `20260422T030122Z-heuristic-heuristic-cv-v1` | heuristic-cv-v1 | n/a (laptop 1) |
| `20260422T030127Z-empty-empty-program` | empty-program | n/a (laptop 1) |
| `20260422T030238Z-codex-gpt-5-4` | gpt-5.4 | 0.121.0 (laptop 1) |
| `20260422T035450Z-codex-gpt-5-3-codex` | gpt-5.3-codex | 0.121→0.122 (laptop 1) |
| `20260423T104654Z-codex-gpt-5-4-mini` | gpt-5.4-mini | 0.122.0 stable (laptop 2) |

**DO NOT RE-RUN any of these.** Each multimodal sweep costs ~1.5 hours of
ChatGPT Pro quota; all results are already on disk.

Headline numbers (from `paper/tables/main_results.csv`, sorted by overall EM):

| Model | Exact | PixAcc | FG-IoU | Parse |
|---|---|---|---|---|
| Heuristic-CV | **0.087** | 0.881 | 0.583 | 1.000 |
| gpt-5.3-codex | 0.047 | 0.947 | 0.761 | 0.973 |
| gpt-5.4-mini | 0.040 | 0.827 | 0.536 | 0.867 |
| gpt-5.4 | 0.013 | 0.961 | **0.845** | 0.973 |
| Empty-Program | 0 | 0 | 0 | 0 |

Notable asymmetries:
- gpt-5.4-mini is the **only** system with non-zero EM on medium (0.04) AND
  hard (0.02) tiers, but its overall EM (0.04) is still below gpt-5.3-codex
  (0.047) because of lower easy-tier EM (0.06 vs 0.12).
- gpt-5.4-mini's FG-IoU is surprisingly low: 0.593 easy / 0.615 medium /
  **0.399 hard** — below the heuristic on easy (0.745) and hard (0.489).
- gpt-5.4-mini's hard-tier parse_success drops to 0.62 (7 timeout, 7
  empty_program, 12 out_of_range on hard).
- CI overlap: gpt-5.3-codex EM [0.013, 0.080] vs mini EM [0.013, 0.073] —
  "mini lower than gpt-5.3-codex" is NOT statistically significant.

## 4. What's already done this push

- `paper/sections/abstract.tex` rewritten around the tier-dependent
  crossover. Key phrasing: "the heuristic leads easy-tier exact match (0.26
  vs. at most 0.12 for any multimodal model) ... *the strongest multimodal
  model* retains most of the spatial structure and leads foreground IoU on
  every tier (up to 0.87) ... best overall exact match is 0.047." The
  qualifier "strongest multimodal model" is there because mini's FG-IoU
  does NOT lead every tier — only gpt-5.4 does.
- `paper/sections/intro.tex` contribution #4 updated to cite the 3
  headline numbers (0.87 FG-IoU cap / 0.047 overall EM cap / 0.26
  heuristic easy EM).
- `docs/REPRODUCIBILITY.md §8` records the CLI pin narrative.
- `paper/tables/*.tex` and `paper/figures/*.pdf` regenerated from all 5
  summaries.
- `paper/main.pdf` rebuilt (12 pages, 494KB). **Awaits Shivam's review.**

## 5. What's pending (in priority order)

1. **Shivam's review of `paper/main.pdf`.** Do not commit or `make arxiv`
   until he signs off.
2. **LaTeX float warning** on `analysis.tex` line 54 (qualitative-grid
   figure) — "Float too large for page by 494.65569pt". Build succeeded,
   paper is 12 pages, but placement around the grid may be tight.
3. *Optional:* **`analysis.tex §5.4` qualifier.** Shivam's text says
   "multimodal models retain most of the spatial structure (foreground IoU
   stays roughly flat across tiers)". True for gpt-5.4 (0.868→0.812) but
   FALSE for mini (0.593→0.399). **Do NOT edit §5.4 unsolicited** —
   Shivam wrote it. If he asks, add a qualifier like "for the stronger
   multimodal models".
4. *Optional:* sentence in `analysis.tex §5.1` (error taxonomy) noting
   mini's hard-tier parse collapse (0.62 vs 0.92 for gpt-5.3-codex).
   Shivam hasn't decided.
5. *Optional:* mention CI overlap when discussing the EM ranking.
6. **Build arxiv tarball** — `/bin/zsh -lc 'cd paper && make arxiv'`
   produces `paper/main-arxiv.tar.gz`. **Only after Shivam signs off.**

## 6. Hard guardrails (do not violate)

- **No commits or pushes to `main`.** Work stays on
  `wip-transfer-2026-04-23`; Shivam cherry-picks onto main at the end.
- **No commits until Shivam reviews `paper/main.pdf`.** Exception: if he
  explicitly asks to transfer again via this WIP branch.
- **No OpenAI API calls.** All LLM eval via `codex exec`.
- **Do not re-run any of the 5 sweeps.** Summary.json is on disk.
- **Do not touch `data/eval_v1/`** — seeded PNGs, SHA256SUMS-pinned; any
  change invalidates eval_v1.
- **Do not revert Shivam's edits to `paper/sections/analysis.tex §5.4`.**
  The crossover narrative is his.

## 7. Files / paths quick-ref

- Paper sections: `paper/sections/{abstract,intro,related,benchmark,experiments,analysis,limitations}.tex`
- Tables (auto-generated): `paper/tables/main_results.{csv,tex}`,
  `paper/tables/error_taxonomy.{csv,tex}`
- Figures (auto-generated): `paper/figures/fig_*.pdf`
- Paper build: `paper/Makefile` — targets `make`, `make clean`, `make arxiv`
- Analysis pipeline (idempotent):
  `uv run python scripts/analyze.py && uv run python scripts/make_figures.py`
- Sweep script (do not run): `scripts/run_codex_sweep.sh`
- Run artifacts: `data/runs/<timestamp>-<provider>-<model>/summary.json` +
  `samples/*.json`
- Eval dataset (frozen, do not touch): `data/eval_v1/eval/{easy,medium,hard}/`
- Reproducibility doc: `docs/REPRODUCIBILITY.md`

## 8. First thing to do on resume

```bash
git branch --show-current           # wip-transfer-2026-04-23
git log -1 --oneline                # 7fbf7a3 or later
# Environment setup per §2 above.
```

Then ask Shivam: **"Have you reviewed paper/main.pdf? Any changes, or
should I run `make arxiv`?"**
- If changes: make them, rebuild, ask for re-review.
- If sign-off: `make arxiv`, hand over the tarball.
- If not yet: wait.

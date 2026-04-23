# Resume Notes — ui-bench → arXiv push

Paused at **2026-04-22 22:41 local** (IST). User logging off.

**Update @ 22:48:** User asked for all processes stopped (switching to another
macOS user for company VPN). I killed pid 60295 and its codex-exec child. The
`gpt-5.4-mini` run is therefore frozen at **110/150** with no summary.json.
On resume, follow §2 "Process dead and <150 samples" branch.

## 1. Sweep state at pause

All 5 runs are writing to `data/runs/`:

| Run dir | Samples | `summary.json`? |
|---|---|---|
| `20260422T030122Z-heuristic-heuristic-cv-v1` | 150/150 | yes |
| `20260422T030127Z-empty-empty-program` | 150/150 | yes |
| `20260422T030238Z-codex-gpt-5-4` | 150/150 | yes |
| `20260422T035450Z-codex-gpt-5-3-codex` | 150/150 | yes |
| `20260422T080708Z-codex-gpt-5-4-mini` | **110/150** | no — still running |

The original `bash scripts/run_codex_sweep.sh` orchestrator (pid 15609) was
`kill -STOP`ped after `gpt-5.4` finished and then `kill -9`ed by my monitor when
`gpt-5.3-codex` summary.json appeared. It's gone.

`gpt-5.4-mini` is being driven by a **parallel, nohup+disown'd** `uv run` I
launched directly:

- uv process: `pid 60295`, cwd `/Users/shivamkumar/projects/personal/ui-bench`
- stdout/stderr: `data/runs/.mini-parallel.log`
- command:
  ```
  uv run ui-bench run --dataset-dir data/eval_v1/eval --provider codex \
    --codex-model gpt-5.4-mini --codex-timeout-seconds 240 \
    --output-dir data/runs
  ```

Tier progress at pause: easy 50/50, hard 50/50, medium 10/50.

Medium tier is pacing ~2 min/sample, so the remaining 40 samples ≈ **~1h20m**
if nothing kills it.

## 2. First thing to check on resume

```bash
cd /Users/shivamkumar/projects/personal/ui-bench
ls data/runs/20260422T080708Z-codex-gpt-5-4-mini/samples/ | wc -l   # 150?
ls data/runs/20260422T080708Z-codex-gpt-5-4-mini/summary.json       # exists?
ps -p 60295 -o pid,stat,command                                      # still alive?
tail -10 data/runs/.mini-parallel.log                                # recent output?
```

Branches:

- **All 150 + summary.json present** → jump to §3.
- **Process alive but <150** → let it continue, poll every ~15 min.
- **Process dead and <150 samples** → relaunch just the remaining tail:
  ```bash
  nohup uv run ui-bench run --dataset-dir data/eval_v1/eval --provider codex \
    --codex-model gpt-5.4-mini --codex-timeout-seconds 240 \
    --output-dir data/runs > data/runs/.mini-parallel-2.log 2>&1 &
  disown
  ```
  (That creates a second mini run dir; analyze.py will pick up whichever has
  summary.json, so delete the incomplete one before running analysis:
  `rm -rf data/runs/20260422T080708Z-codex-gpt-5-4-mini` once the new run
  completes.)

## 3. Remaining paper-push workflow (~20 min of active work)

Order matters — do in sequence:

```bash
uv run python scripts/analyze.py        # writes paper/tables/*.{csv,tex}
uv run python scripts/make_figures.py   # writes paper/figures/*.pdf
cd paper && make clean && make          # produces paper/main.pdf (12-ish pages)
```

Then tighten the abstract + intro (§4 below), rebuild paper, then:

```bash
cd paper && make arxiv                  # produces paper/main-arxiv.tar.gz
```

## 4. Abstract + intro rewrite — key numbers to bake in

From the 4 completed `summary.json` files, the crossover story that the user's
own analysis.tex rewrite already describes is confirmed:

**Per-tier exact-match:**

| System | Easy | Medium | Hard |
|---|---|---|---|
| Heuristic-CV | **0.26** | 0.00 | 0.00 |
| Empty-Program | 0.00 | 0.00 | 0.00 |
| gpt-5.4 | 0.04 | 0.00 | 0.00 |
| gpt-5.3-codex | 0.12 | 0.02 | 0.00 |
| gpt-5.4-mini | TBD after sweep | TBD | TBD |

**Per-tier foreground IoU:**

| System | Easy | Medium | Hard |
|---|---|---|---|
| Heuristic-CV | 0.745 | 0.515 | 0.489 |
| gpt-5.4 | **0.868** | **0.854** | **0.812** |
| gpt-5.3-codex | 0.799 | 0.776 | 0.708 |
| gpt-5.4-mini | TBD | TBD | TBD |

**Overall:**

| System | Exact | FG-IoU | Parse |
|---|---|---|---|
| Heuristic-CV | 0.087 | 0.583 | 1.000 |
| gpt-5.4 | 0.013 | 0.845 | 0.973 |
| gpt-5.3-codex | 0.047 | 0.761 | 0.973 |

Headline framing (aligns with user's edits to `paper/sections/analysis.tex`,
§5.4):

1. **Crossover:** Heuristic wins easy-tier exact-match; LLM wins FG-IoU on
   every tier.
2. LLMs recover the right shape list but drift on integer parameters → miss
   exact-match on easy despite higher IoU.
3. Heuristic collapses on medium/hard because overlapping shapes merge into
   single connected components.
4. Benchmark is **not saturated**: best overall EM is ~0.05 (gpt-5.3-codex).

Target edits:

- `paper/sections/abstract.tex` — replace the current "no model matches the
  heuristic on foreground IoU" line (that claim is wrong). Lead with the
  crossover. Keep ≤150 words.
- `paper/sections/intro.tex` — contribution #4 should cite the best exact-match
  number, the heuristic easy-tier exact-match number, and the best FG-IoU.

## 5. Edits I already made this session

- `paper/references.bib`: 4 entries had `{LastName, Others}` which rendered as
  "Others LastName" in the bbl. Changed to `{LastName and others}` → now renders
  as "LastName et al." (rismanchian, roberts, lin, zhou).
- `paper/sections/experiments.tex` and `paper/sections/analysis.tex`: all
  `\begin{figure}[h]` → `\begin{figure}[!htbp]` (plus the main-results table)
  to prevent the qualitative grid from being pushed past the References section.
- `paper/sections/limitations.tex`: the "Codex non-determinism" paragraph used
  to falsely claim the CLI version was logged in run_config.json; the adapter
  only serializes provider/model/sandbox/timeout/binary/max_retries. Reworded
  to say the CLI versions are documented in REPRODUCIBILITY.md instead.
- `docs/REPRODUCIBILITY.md` §8: added two new bullets —
  (a) the Codex CLI bumped from 0.121.0 → 0.122.0 mid-sweep on the author's
  machine (between gpt-5.4 and gpt-5.4-mini, overlapping gpt-5.3-codex);
  (b) the gpt-5.4-mini sweep was launched in a parallel shell during the tail
  of the gpt-5.3-codex sweep (for wall-clock reasons); the `run_codex_sweep.sh`
  script itself remains serial.

The user edited `paper/sections/analysis.tex` §5.4 ("Heuristic vs. LLM gap")
while I was waiting — it now contains the crossover narrative. **Do not revert
this**; the abstract/intro rewrites should align to it.

## 6. Not-yet-done tasks

- [ ] Run `scripts/analyze.py` once all 3 Codex runs have summary.json.
- [ ] Run `scripts/make_figures.py`.
- [ ] Rebuild paper (`cd paper && make clean && make`).
- [ ] Rewrite abstract + intro contribution #4 using the real numbers (§4 above).
- [ ] Rebuild paper again after rewrite.
- [ ] `cd paper && make arxiv` → produces `paper/main-arxiv.tar.gz`.
- [ ] **Do NOT commit yet** — the user wants to review `paper/main.pdf` first.

## 7. Notable caveats for the paper

- `gpt-5.4` hit `out_of_range` on 4/150 (3 hard + 1 medium). Parse success 0.973.
- `gpt-5.3-codex` hit `timeout` on 2/150 (both hard) and `out_of_range` on
  2/150 hard. Parse success 0.973.
- `gpt-5.4-mini` looked likely to have the highest timeout rate on the hard
  tier (~15–30% of hard samples hit the full 726s retry cascade). Check the
  final `adapter_error_type_counts` in its summary.json.
- The qualitative-grid figure will auto-pick the best-EM Codex run — that is
  currently `gpt-5.3-codex` (0.047 overall). If gpt-5.4-mini turns out higher,
  it'll flip. Figure caption in `paper/sections/analysis.tex` already reads
  "the strongest Codex-backed model", which is generic enough.

## 8. Files/paths quick-ref

- Sweep script (serial, for the repro path): `scripts/run_codex_sweep.sh`
- Eval dataset: `data/eval_v1/eval/{easy,medium,hard}/` (150 PNGs + SHA256SUMS)
- Run artifacts: `data/runs/<timestamp>-<provider>-<model>/`
- Analysis: `scripts/analyze.py`, `scripts/make_figures.py`
- Paper source: `paper/main.tex`, `paper/sections/*.tex`, `paper/references.bib`
- Paper build: `paper/Makefile` (`make`, `make clean`, `make arxiv`)
- Repro doc: `docs/REPRODUCIBILITY.md`
- Mini-run live log: `data/runs/.mini-parallel.log`

## 9. Current task list (Claude)

1. [in_progress] Wait for Codex sweep to finish all 3 models
2. [pending] Regenerate analysis tables + figures
3. [pending] Rebuild paper PDF with final numbers
4. [pending] Tighten intro + abstract with real headline numbers
5. [pending] Verify docs/REPRODUCIBILITY.md matches final workflow
6. [pending] Build arXiv tarball

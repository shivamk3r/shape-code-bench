# Research website

The public project website is <https://shivamk3r.github.io/shape-code-bench/>.
Its source is in `website/`, and `.github/workflows/website.yml` builds and
publishes it through GitHub Actions and GitHub Pages on every push to `main`.
Pull requests build and validate the site without deploying it. The workflow
can also be started manually from the repository's Actions tab.

## Build and preview

Use the same Python 3.12 and locked `uv` environment as the benchmark:

```bash
uv sync --frozen --dev
uv run python scripts/build_website.py
uv run python -m http.server 8000 --directory dist
```

Open <http://localhost:8000/website/>. The build writes only public website
files to the git-ignored `dist/website/` directory. The source HTML contains
build tokens; preview the built site rather than opening `website/index.html`
directly. All browser assets use relative URLs so the site works below the
GitHub Pages `/shape-code-bench/` project path.

## Sources and synchronization

The build script uses these authoritative inputs:

- The benchmark generator, difficulty settings, restricted DSL, Pillow
  renderer, and evaluator create all example images and coordinate-shift scores.
  Demo seeds `101`, `202`, and `303` are illustrative scenes outside the frozen
  evaluation seeds `0..49`; the demo makes no model calls.
- `paper/tables/main_results.csv` supplies every published result, confidence
  interval, evaluation count, and headline performance statistic. The complete
  CSV is offered as a download; results retain the paper's named configurations.
- The BibTeX block in `README.md` supplies the displayed and downloadable citation.
- `website/index.html` supplies the research narrative, publication links,
  metadata, protocol description, and quickstart snippets.
- `website/styles.css` and `website/app.js` supply the responsive layout and
  local scene/result controls. The overview, default examples, results, and
  citation remain available without JavaScript.

Update website copy and links in the same change whenever the task, DSL,
generation, difficulty tiers, metrics, providers, results, dataset release,
paper, citation, licensing, or public quickstart changes. Automatic generation
keeps numbers and scenes aligned, but explanatory prose still needs review.
Keep historical paper results clearly labeled, and do not describe them as a
current model leaderboard.

The website publishes no raw model responses, credentials, local configuration,
private publishing drafts, or protected project-management content. The Pages
artifact is `dist/website/`, never the repository root.

## Verification and deployment

```bash
uv run pytest tests/test_website.py
uv run ruff check .
node --check website/app.js
uv run python scripts/build_website.py
```

The website tests check deterministic builds, internal links and anchor IDs,
every demo raster and score against the benchmark implementation, and every
published result against the paper CSV. For layout or interaction changes,
also inspect desktop and mobile views in a browser; exercise tier filters,
coordinate shifts, difference images, confidence intervals, navigation, and
clipboard controls. Check keyboard focus, horizontal overflow, and contrast.

After an authorized push to `main`, confirm the **Research website** workflow
and its `github-pages` deployment succeed, then check the public URL and assets.
GitHub Pages uses the **GitHub Actions** publishing source and HTTPS. No custom
domain or Node build system is required.

## Typography

Manrope is vendored from the Google Fonts `ofl/manrope` directory. Its SIL Open
Font License is preserved in `website/assets/fonts/OFL.txt`. The variable WOFF2
file is served locally; the TTF is a build input for the social preview image
and is excluded from the published artifact. No third-party font requests,
analytics, or runtime service dependencies are used.

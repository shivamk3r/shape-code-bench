"use strict";

document.documentElement.classList.add("js");

const data = JSON.parse(document.getElementById("benchmark-data").textContent);
const state = { tier: "easy", shift: 0, difference: false };
const resultsState = { tier: "all", source: "all" };
const descriptions = {
  easy: "Large primitives, minimal bounding-box overlap, and no clipping.",
  medium: "More primitives, moderate overlap, and limited clipping.",
  hard: "Dense scenes, encouraged overlap, and partial clipping.",
};
const percent = (value, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const titleCase = (text) => text.charAt(0).toUpperCase() + text.slice(1);

const navToggle = document.querySelector(".nav-toggle");
const nav = document.getElementById("primary-nav");
navToggle.addEventListener("click", () => {
  const open = navToggle.getAttribute("aria-expanded") !== "true";
  navToggle.setAttribute("aria-expanded", String(open));
  nav.classList.toggle("is-open", open);
});
nav.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    navToggle.setAttribute("aria-expanded", "false");
    nav.classList.remove("is-open");
  }
});
document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    navToggle.getAttribute("aria-expanded") === "true"
  ) {
    navToggle.setAttribute("aria-expanded", "false");
    nav.classList.remove("is-open");
    navToggle.focus();
  }
});

function updateExample() {
  const example = data.examples[state.tier];
  const variant = example.variants[state.shift];
  const tier = titleCase(state.tier);
  document.querySelectorAll("[data-example-tier]").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.exampleTier === state.tier),
    );
  });
  document.getElementById("scene-metadata").textContent =
    `SEED ${example.seed} / ${example.num_shapes} SHAPES`;
  const target = document.getElementById("target-image");
  target.src = example.target;
  target.alt = `${tier} benchmark target with ${example.num_shapes} shapes, generated from seed ${example.seed}.`;
  const prediction = document.getElementById("prediction-image");
  prediction.src = state.difference ? variant.difference : variant.image;
  prediction.alt = state.difference
    ? `Pixel comparison for the ${tier.toLowerCase()} scene. Shared foreground is dark; differing pixels are orange. First shape shifted by ${state.shift} pixels.`
    : `${tier} reconstruction with the first shape shifted by ${state.shift} pixels. ${variant.exact_match ? "Exact match." : "The rendered pixels differ."}`;
  document.getElementById("prediction-label").textContent = state.difference
    ? "02 / PIXEL DIFFERENCES"
    : "02 / RECONSTRUCTION";
  const differenceToggle = document.getElementById("difference-toggle");
  differenceToggle.setAttribute("aria-pressed", String(state.difference));
  differenceToggle.textContent = state.difference
    ? "Show reconstruction"
    : "Show differences";
  document.getElementById("shift-value").value = `${state.shift} px`;
  const exact = document.getElementById("demo-exact");
  exact.textContent = variant.exact_match ? "Yes" : "No";
  exact.dataset.match = String(variant.exact_match);
  document.getElementById("demo-pixel").textContent = percent(
    variant.pixel_accuracy,
    2,
  );
  document.getElementById("demo-iou").textContent = percent(
    variant.foreground_iou,
    2,
  );
  document.getElementById("example-program").textContent =
    variant.program.trimEnd();
  const description = document.getElementById("tier-description");
  const strong = document.createElement("strong");
  strong.textContent = `${tier} · ${example.min_shapes}–${example.max_shapes} shapes. `;
  description.replaceChildren(
    strong,
    document.createTextNode(descriptions[state.tier]),
  );
}

document.querySelectorAll("[data-example-tier]").forEach((button) => {
  button.addEventListener("click", () => {
    state.tier = button.dataset.exampleTier;
    updateExample();
  });
});
document
  .getElementById("coordinate-shift")
  .addEventListener("input", (event) => {
    state.shift = Number(event.target.value);
    updateExample();
  });
document.getElementById("difference-toggle").addEventListener("click", () => {
  state.difference = !state.difference;
  updateExample();
});

function updateResults(announce = true) {
  const { tier, source } = resultsState;
  const rows = data.results
    .filter((row) => row.difficulty === tier && (
      source === "all" || data.evaluations[row.evaluation_id].kind === source
    ))
    .sort((a, b) => b.mean_foreground_iou - a.mean_foreground_iou);
  const body = document.getElementById("results-body");
  body.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    const name = document.createElement("span");
    name.className = "model-name";
    name.textContent = row.display_name;
    th.append(name);
    const detail = document.createElement("span");
    detail.className = "model-detail";
    detail.textContent = row.configuration;
    th.append(detail);
    const evaluation = data.evaluations[row.evaluation_id];
    const badge = document.createElement("a");
    badge.className = "evaluation-badge";
    badge.href = `#${evaluation.protocol_id}`;
    badge.dataset.evaluationProtocol = evaluation.protocol_id;
    badge.textContent = evaluation.label;
    badge.setAttribute("aria-label",
      `${row.display_name} · ${row.configuration}: ${evaluation.label}, protocol and downloads`);
    th.append(badge);
    tr.append(th);
    [
      "exact_match_rate",
      "mean_pixel_accuracy",
      "mean_foreground_iou",
      "parse_success_rate",
    ].forEach((metric) => {
      const td = document.createElement("td");
      if (metric === "mean_foreground_iou") {
        const bar = document.createElement("span");
        bar.className = "score-bar";
        bar.style.setProperty("--score", percent(row[metric], 4));
        td.append(bar);
      }
      const value = document.createElement("span");
      value.className = "score-value";
      value.textContent = percent(row[metric]);
      const confidence = document.createElement("span");
      confidence.className = "confidence";
      confidence.textContent = `[${(row[`${metric}_ci_low`] * 100).toFixed(1)}, ${(row[`${metric}_ci_high`] * 100).toFixed(1)}]`;
      td.append(value, confidence);
      tr.append(td);
    });
    body.append(tr);
  });
  document.querySelectorAll("[data-results-tier]").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.resultsTier === tier),
    );
  });
  const label = tier === "all" ? "All tiers" : titleCase(tier);
  const sourceLabel = document.getElementById("results-source").selectedOptions[0].textContent;
  const caption = `${label} · ${rows.length} configurations · ${rows[0]?.n ?? 0} samples each · ${sourceLabel} · sorted by foreground IoU`;
  document.getElementById("results-caption").textContent = caption;
  if (announce) document.getElementById("results-status").textContent = caption;
  const multimodal = rows.filter((row) => ["codex", "claude", "openai"].includes(row.provider));
  for (const [id, metric] of [["exact", "exact_match_rate"], ["iou", "mean_foreground_iou"]]) {
    const best = multimodal.reduce((winner, row) =>
      !winner || row[metric] > winner[metric] ? row : winner, null);
    const score = document.getElementById(`best-${id}-score`);
    score.replaceChildren(document.createTextNode(best ? (best[metric] * 100).toFixed(1) : "—"));
    if (best) {
      const unit = document.createElement("span");
      unit.textContent = "%";
      score.append(unit);
    }
    document.getElementById(`best-${id}-name`).textContent = best
      ? `${best.display_name} · ${best.configuration}` : "No multimodal results in this selection";
    document.getElementById(`best-${id}-scope`).textContent =
      `${label} · ${best?.n ?? 0} scenes · ${sourceLabel}`;
  }
}

document.querySelectorAll("[data-results-tier]").forEach((button) => {
  button.addEventListener("click", () => {
    resultsState.tier = button.dataset.resultsTier;
    updateResults();
  });
});

document.getElementById("results-source").addEventListener("change", (event) => {
  resultsState.source = event.target.value;
  updateResults();
});
document
  .getElementById("show-confidence")
  .addEventListener("change", (event) => {
    document
      .getElementById("results-table-wrapper")
      .classList.toggle("show-ci", event.target.checked);
  });

document.addEventListener("click", (event) => {
  const badge = event.target.closest("[data-evaluation-protocol]");
  if (badge) document.getElementById(badge.dataset.evaluationProtocol).open = true;
});
function openLinkedProtocol() {
  const panel = document.getElementById(window.location.hash.slice(1));
  if (panel?.matches(".evaluation-protocol")) panel.open = true;
}
window.addEventListener("hashchange", openLinkedProtocol);
openLinkedProtocol();
updateResults(false);

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Some browsers restrict clipboard permissions; retain a local fallback.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.className = "sr-only";
  textarea.setAttribute("readonly", "");
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard unavailable");
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  const original = button.innerHTML;
  let resetTimer;
  button.addEventListener("click", async () => {
    clearTimeout(resetTimer);
    try {
      await copyText(
        document.getElementById(button.dataset.copy).textContent.trim(),
      );
      button.textContent = "Copied ✓";
      document.getElementById("copy-status").textContent =
        "Copied to clipboard.";
    } catch {
      button.textContent = "Select to copy";
      const range = document.createRange();
      range.selectNodeContents(document.getElementById(button.dataset.copy));
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      document.getElementById("copy-status").textContent =
        "Text selected. Use your browser’s copy command.";
    }
    resetTimer = setTimeout(() => {
      button.innerHTML = original;
    }, 2000);
  });
});

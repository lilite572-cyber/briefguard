"""Derive README results and diagnostic error tables from actual run artifacts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from briefguard.runner import read_rows

summary = json.loads((ROOT / "results/test/summary.json").read_text())
meta = json.loads((ROOT / "results/test/metadata.json").read_text())
config = meta["identity"]["config"]
primary = summary["budgets"][str(summary["primary_budget"])]
rows = [r for r in read_rows(ROOT / "results/test/predictions.jsonl") if r["budget"] == summary["primary_budget"]]
methods = config["methods"]
first = primary["methods"][methods[0]]
u = primary["uncertainty"]
lines = [f"Held-out run `{meta['run_id']}`: **{u['source_clusters']} source groups**, "
         f"**{first['n']} clips** ({first['n_violating']} violating, {first['n_clean']} clean), "
         f"**{meta['rows']:,} recorded checks** across the prespecified budgets. Primary budget: "
         f"**{summary['primary_budget']} frames per clip**.", "",
         "| Method | Violation recall | Event coverage (diagnostic) | Median CPU check time, including prepass |",
         "|---|---:|---:|---:|"]
for m in methods:
    s = primary["methods"][m]
    lines.append(f"| {m} | {s['recall']*100:.2f}% | {s['sampling_coverage']*100:.2f}% | {s['latency_median_ms']:.2f} ms |")
lines += ["", "Paired source-cluster bootstrap recall differences (percentage points, 95% intervals):", ""]
for name, v in u["recall_differences"].items():
    lines.append(f"- `{name}`: **{100*v['estimate']:+.2f}** [{100*v['ci95'][0]:+.2f}, {100*v['ci95'][1]:+.2f}].")
lines += ["", f"The prespecified hypothesis is **{'supported' if summary['hypothesis_supported'] else 'not supported'}**: "
          "an advantage over uniform selection alone is insufficient; it must also beat the simple change baseline.", "",
          f"Measured test execution: {meta['invocation_wall_s']:.2f} s, "
          f"peak process RSS {meta['peak_rss_bytes']/1024**2:.1f} MiB, "
          f"external API spend ${meta['api_spend_usd']:.2f}. "
          "These are recorded host observations, not cross-machine performance guarantees. "
          "Resource figures exclude environment installation and image illustration generation.", "",
          "Every value above derives from `results/test/summary.json`, `metadata.json`, and the compressed predictions; "
          "regenerate this block with `python scripts/update_readme.py`."]
readme = (ROOT / "README.md").read_text()
start, end = "<!-- BEGIN GENERATED RESULTS -->", "<!-- END GENERATED RESULTS -->"
before, tail = readme.split(start, 1)
_, after = tail.split(end, 1)
(ROOT / "README.md").write_text(before + start + "\n" + "\n".join(lines) + "\n" + end + after)

error = ["# Error analysis", "", f"Derived from held-out run `{meta['run_id']}` at K={summary['primary_budget']}. "
         "All slices below were prespecified, are descriptive, and were not used to tune the algorithm.", "",
         "## Separate sampling misses from checker misses", "",
         "| Method | All false approvals | Event absent from selection | Event captured but checker missed |",
         "|---|---:|---:|---:|"]
for m in methods:
    misses = [r for r in rows if r["method"] == m and r["annotation"]["violated"] and r["prediction"]["status"] == "pass"]
    covered = sum(r["sampling_hit"] is True for r in misses)
    error.append(f"| {m} | {len(misses)} | {len(misses)-covered} | {covered} |")
for dim in ("duration_frames", "violation_type", "motion", "severity"):
    error += ["", f"## Descriptive slice: {dim}", "",
              "| Slice | Uniform recall | Change recall | Adaptive recall | Uniform coverage | Change coverage | Adaptive coverage |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    def pct(x): return "n/a" if x is None else f"{100*x:.2f}%"
    for value, group in primary["descriptive_slices"][dim].items():
        vals = [pct(group[m][key]) for key in ("recall", "sampling_coverage") for m in methods]
        error.append("| " + value + " | " + " | ".join(vals) + " |")
error += ["", "## Concrete examples", "",
          "The temporal interval is half-open; a selected exit frame is already compliant. These examples are deterministic "
          "first matches in the saved rows, not a random audit sample.", ""]
for m in methods:
    for captured in (False, True):
        r = next(r for r in rows if r["method"] == m and r["annotation"]["violated"]
                 and r["prediction"]["status"] == "pass" and r["sampling_hit"] is captured)
        a = r["annotation"]
        error.append(f"- `{m}`, `{r['clip_id']}`: {a['severity']} {a['violation_type']}, "
                     f"event [{a['start_frame']},{a['end_frame']}), selected {r['selected_indices']}; "
                     f"{'captured but missed by checker' if captured else 'not captured'}.")
error += ["", "## Interpretation and limits", "",
          "The checker's tolerance thresholds deliberately miss all subtle fixture variants. This ceiling is an engineered "
          "diagnostic, not evidence that a VLM would miss them. The adaptive method also loses event coverage on some "
          "longer, color-change and subtle slices: local novelty plus coverage anchors is not uniformly protective. "
          "Distractor sensitivity and downsampling may explain failures, but this run contains no causal ablation proving "
          "which component is responsible.", "",
          "Zero observed false alarms on the small, easy clean control set must not be read as zero population risk; "
          "the bootstrap interval can degenerate at zero when no events occur. Natural errors, camera motion, occlusions, "
          "typography/OCR and human perceptual validity remain unevaluated. An actionable next study should freeze "
          "new source groups, add human temporal labels, and compare a common VLM checker with audited total costs. "
          "Do not reuse these held-out seeds as an untouched test after further tuning.", ""]
(ROOT / "docs/error_analysis.md").write_text("\n".join(error))

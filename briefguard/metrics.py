"""Explicit-denominator metrics and paired source-cluster uncertainty."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def _ratio(a, b):
    return float(a / b) if b else None


def score(rows: list[dict]) -> dict:
    known = [r for r in rows if r["annotation"].get("violated") in (True, False)]
    positive = [r for r in known if r["annotation"]["violated"] is True]
    negative = [r for r in known if r["annotation"]["violated"] is False]
    tp = sum(r["prediction"]["violated"] is True for r in positive)
    fp = sum(r["prediction"]["violated"] is True for r in negative)
    approved = [r for r in known if r["prediction"]["status"] == "pass"]
    false_pass = sum(r["annotation"]["violated"] is True for r in approved)
    fn = len(positive) - tp
    tn = len(negative) - fp
    return {
        "n": len(rows), "known_gt": len(known), "unknown_gt": len(rows) - len(known),
        "n_violating": len(positive), "n_clean": len(negative),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "recall": _ratio(tp, len(positive)), "miss_rate": _ratio(fn, len(positive)),
        "false_approval_rate": _ratio(false_pass, len(positive)),
        "false_alarm_rate": _ratio(fp, len(negative)),
        "approval_contamination": _ratio(false_pass, len(approved)),
        "sampling_coverage": _ratio(sum(r["sampling_hit"] is True for r in positive), len(positive)),
        "abstention_rate": _ratio(sum(r["prediction"]["status"] == "indeterminate" for r in rows), len(rows)),
        "approved": len(approved), "false_pass": false_pass,
    }


def _source_arrays(groups: dict[str, list[dict]], metric: str, source_ids: list[int]):
    arrays = {}
    for method, rows in groups.items():
        buckets = defaultdict(list)
        for row in rows:
            buckets[row["source_id"]].append(row)
        if set(buckets) != set(source_ids):
            raise ValueError("All methods must contain identical source clusters")
        # Metrics' denominators can vary by source: retain numerators and denominators
        # rather than averaging rates or dropping sources with zero denominators.
        pairs = []
        for source_id in source_ids:
            s = score(buckets[source_id])
            mapping = {
                "recall": (s["tp"], s["n_violating"]),
                "false_alarm_rate": (s["fp"], s["n_clean"]),
                "false_approval_rate": (s["false_pass"], s["n_violating"]),
                "sampling_coverage": (sum(r["sampling_hit"] is True for r in buckets[source_id]
                                           if r["annotation"].get("violated") is True), s["n_violating"]),
            }
            pairs.append(mapping[metric])
        arrays[method] = np.asarray(pairs, dtype=float)
    return arrays


def clustered_intervals(groups: dict[str, list[dict]], resamples=2000, seed=572) -> dict:
    """Resample sources, jointly across methods; keep all sibling observations."""
    if resamples < 1 or not groups:
        raise ValueError("Positive resamples and nonempty methods required")
    first = next(iter(groups.values()))
    source_ids = sorted({r["source_id"] for r in first})
    if not source_ids:
        raise ValueError("No sources")
    reference_keys = {(r["source_id"], r["clip_id"]) for r in first}
    if len(reference_keys) != len(first):
        raise ValueError("Duplicate observations")
    for rows in groups.values():
        keys = {(r["source_id"], r["clip_id"]) for r in rows}
        if keys != reference_keys or len(keys) != len(rows):
            raise ValueError("Paired methods must contain exactly the same unique clips")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(source_ids), size=(resamples, len(source_ids)))
    out = {"source_clusters": len(source_ids), "resamples": resamples, "seed": seed,
           "method_intervals": {}, "recall_differences": {}}
    for metric in ("recall", "false_alarm_rate", "false_approval_rate", "sampling_coverage"):
        arrays = _source_arrays(groups, metric, source_ids)
        samples = {}
        for method, a in arrays.items():
            totals = a[draws].sum(axis=1)
            valid = totals[:, 1] > 0
            v = np.full(resamples, np.nan)
            v[valid] = totals[valid, 0] / totals[valid, 1]
            samples[method] = v
            ci = [float(x) for x in np.nanquantile(v, [.025, .975])] if valid.any() else None
            out["method_intervals"].setdefault(method, {})[metric] = ci
        if metric == "recall" and "adaptive" in samples:
            for baseline in ("uniform", "change"):
                if baseline in samples:
                    delta = samples["adaptive"] - samples[baseline]
                    out["recall_differences"][f"adaptive_minus_{baseline}"] = {
                        "estimate": score(groups["adaptive"])["recall"] - score(groups[baseline])["recall"],
                        "ci95": [float(x) for x in np.nanquantile(delta, [.025, .975])],
                    }
    return out


def summarize(rows: list[dict], config: dict) -> dict:
    if not rows or any("error" in r for r in rows):
        raise ValueError("Cannot summarize empty or failed experiment")
    budgets = {}
    for budget in config["budgets"]:
        groups = {method: [r for r in rows if r["method"] == method and r["budget"] == budget]
                  for method in config["methods"]}
        metrics = {m: score(rs) for m, rs in groups.items()}
        for method, rs in groups.items():
            times = [sum(r["timing"][k] for k in ("prepass_s", "selection_s", "verification_s")) for r in rs]
            metrics[method]["latency_median_ms"] = float(np.median(times) * 1000)
            metrics[method]["latency_p95_ms"] = float(np.quantile(times, .95) * 1000)
            for part in ("generation_s", "prepass_s", "selection_s", "verification_s"):
                metrics[method][part + "_median"] = float(np.median([r["timing"][part] for r in rs]))
            metrics[method]["prepass_frames"] = rs[0]["resources"]["prepass_frames"]
            metrics[method]["checked_frames"] = rs[0]["resources"]["checked_frames"]
        uncertainty = clustered_intervals(groups, config["bootstrap_resamples"], config["bootstrap_seed"])
        slices = {}
        for dimension in ("duration_frames", "violation_type", "motion", "severity"):
            values = sorted({str(r["annotation"].get(dimension)) for r in next(iter(groups.values()))})
            slices[dimension] = {value: {m: score([r for r in rs if str(r["annotation"].get(dimension)) == value])
                                        for m, rs in groups.items()} for value in values}
        budgets[str(budget)] = {"methods": metrics, "uncertainty": uncertainty, "descriptive_slices": slices}
    primary = budgets[str(config["primary_budget"])]["uncertainty"]["recall_differences"]
    supported = len(primary) == 2 and all(x["ci95"][0] > 0 for x in primary.values())
    return {"primary_budget": config["primary_budget"], "hypothesis_supported": supported,
            "interpretation": "Controlled synthetic results only; no real-video or VLM validation.",
            "budgets": budgets}


def write_report(summary: dict, directory: Path):
    """Tables are derived from saved row data; no hand-entered experiment values."""
    lines = ["# Measured results", "", "Generated by `python -m briefguard report`. Synthetic CPU study only.", "",
             "| K | Method | Violation recall | False approvals / violating | False alarms / clean | Event coverage | Median ms | p95 ms |",
             "|---:|---|---:|---:|---:|---:|---:|---:|"]
    def pct(value):
        return "n/a" if value is None else f"{100 * value:.2f}%"
    for k, group in summary["budgets"].items():
        for method, s in group["methods"].items():
            lines.append(f"| {k} | {method} | {pct(s['recall'])} | {pct(s['false_approval_rate'])} | "
                         f"{pct(s['false_alarm_rate'])} | {pct(s['sampling_coverage'])} | "
                         f"{s['latency_median_ms']:.3f} | {s['latency_p95_ms']:.3f} |")
    primary = summary["budgets"][str(summary["primary_budget"])]["uncertainty"]
    lines += ["", f"Primary budget: {summary['primary_budget']}. Source clusters: {primary['source_clusters']}.",
              "", "Paired source-cluster bootstrap recall differences (percentage points; 95% intervals):", ""]
    for name, d in primary["recall_differences"].items():
        lines.append(f"- {name}: {d['estimate'] * 100:.2f} [{d['ci95'][0] * 100:.2f}, {d['ci95'][1] * 100:.2f}]")
    lines += ["", f"Prespecified hypothesis supported: **{summary['hypothesis_supported']}**.", "",
              "Latency includes each method's own complete prepass, selection and verification; generation is stored separately. "
              "Timings are original cold component observations retained on resume, not timing a cached replay. "
              "Same checker-frame budget does not imply same total computation. Human review pending.", ""]
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (directory / "tables.md").write_text("\n".join(lines))

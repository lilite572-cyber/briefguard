"""Export a local, evidence-only replay of a completed benchmark run.

The viewer renders the exact generated RGB frames from a lossless sprite sheet.
It neither calls a model nor changes run results. All cases are illustrative,
selected after the run, and must not be treated as a second test set.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _read_rows(result_dir: Path) -> tuple[list[dict[str, Any]], Path]:
    for name in ("predictions.jsonl", "predictions.jsonl.gz", "results.jsonl", "results.jsonl.gz", "records.jsonl"):
        path = result_dir / name
        if path.is_file():
            content = gzip.decompress(path.read_bytes()).decode("utf-8") if path.suffix == ".gz" else path.read_text()
            rows = [json.loads(line) for line in content.splitlines() if line.strip()]
            if not rows:
                raise ValueError(f"No completed predictions in {path}")
            return rows, path
    raise FileNotFoundError(f"No predictions.jsonl or results.jsonl in {result_dir}")


def _violated(row: dict[str, Any]) -> bool | None:
    return row.get("prediction", {}).get("violated")


def _is_positive(row: dict[str, Any]) -> bool:
    return row.get("annotation", {}).get("violated") is True


def choose_cases(rows: list[dict[str, Any]], limit: int = 6) -> list[tuple[str, str]]:
    """Choose transparent illustrative cases, with no effect on aggregate metrics."""
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in sorted(rows, key=lambda r: (str(r["clip_id"]), r["method"])):
        groups[str(row["clip_id"])][row["method"]] = row
    selected: list[tuple[str, str]] = []

    def add_first(predicate: Any, reason: str) -> None:
        used = {key for key, _ in selected}
        for key, methods in groups.items():
            if key not in used and predicate(methods):
                selected.append((key, reason))
                return

    def representative(methods: dict[str, Any]) -> dict[str, Any]:
        return next(iter(methods.values()))

    add_first(lambda m: not _is_positive(representative(m)), "Compliant control")
    add_first(lambda m: "adaptive" in m and _is_positive(m["adaptive"]) and _violated(m["adaptive"]) is False,
              "Adaptive false approval")
    add_first(lambda m: any(_is_positive(r) and r.get("sampling_hit") is True and _violated(r) is False for r in m.values()),
              "Evidence sampled, checker missed")
    add_first(lambda m: "adaptive" in m and "uniform" in m and _violated(m["adaptive"]) is True and _violated(m["uniform"]) is False,
              "Adaptive caught, uniform missed")
    add_first(lambda m: representative(m).get("annotation", {}).get("violation_type") == "label_corruption",
              "Brief-critical label change")
    add_first(lambda m: representative(m).get("annotation", {}).get("violation_type") == "wrong_color",
              "Packaging color change")
    add_first(lambda m: representative(m).get("annotation", {}).get("motion") == "distractor" and _is_positive(representative(m)),
              "Distracting background motion")
    for key in groups:
        if len(selected) >= limit:
            break
        if key not in {item[0] for item in selected}:
            selected.append((key, "Additional illustrative case"))
    return selected[:limit]


def _summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    methods: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        methods[row["method"]].append(row)
    summary = []
    for method, values in sorted(methods.items()):
        positives = [r for r in values if _is_positive(r)]
        negatives = [r for r in values if r.get("annotation", {}).get("violated") is False]
        tp = sum(_violated(r) is True for r in positives)
        fn = sum(_violated(r) is False for r in positives)
        fp = sum(_violated(r) is True for r in negatives)
        tn = sum(_violated(r) is False for r in negatives)
        costs = []
        for row in values:
            timing = row.get("timing", {})
            costs.append(sum(float(timing.get(key, 0)) for key in
                             ("prepass_s", "selection_s", "verification_s")))
        summary.append({"method": method, "n_clips": len(values), "tp": tp, "fn": fn,
                        "fp": fp, "tn": tn, "positive_count": len(positives),
                        "negative_count": len(negatives),
                        "recall": tp / len(positives) if positives else None,
                        "false_approval_rate": fn / len(positives) if positives else None,
                        "false_positive_rate": fp / len(negatives) if negatives else None,
                        "mean_pipeline_ms": 1000 * sum(costs) / len(costs) if costs else None})
    return summary


def export_demo(result_dir: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Export exact-frame assets and replay JSON for up to six completed cases.

    ``config`` must be the generation configuration used by the run. It can be
    either flat or contain a ``data`` or ``dataset`` object. A frame hash saved
    by the runner is checked when available, so incompatible replay fails.
    """
    from .data import iter_clips

    import hashlib

    result_dir, output_dir = Path(result_dir), Path(output_dir)
    rows, source_path = _read_rows(result_dir)
    budget = int(config.get("demo_budget", 8))
    available = sorted({int(r["budget"]) for r in rows})
    if budget not in available:
        budget = available[0]
    rows = [r for r in rows if int(r["budget"]) == budget]
    # Prefer held-out test if a directory contains multiple splits.
    if any(r.get("split") == "test" for r in rows):
        rows = [r for r in rows if r.get("split") == "test"]
    selected = choose_cases(rows)
    groups: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        groups[str(row["clip_id"])][row["method"]] = row
    generation_config = config.get("data", config.get("dataset", config))
    fps = int(generation_config.get("fps", 24))
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = output_dir / "assets"
    assets.mkdir(exist_ok=True)
    template = Path(__file__).resolve().parents[1] / "demo" / "index.html"
    if template.resolve() != (output_dir / "index.html").resolve():
        shutil.copyfile(template, output_dir / "index.html")

    clips_out = []
    # Generate only selected clips and release frames after each source.
    by_source: dict[int, set[str]] = defaultdict(set)
    reasons = dict(selected)
    for clip_id, _ in selected:
        by_source[int(next(iter(groups[clip_id].values()))["source_id"])].add(clip_id)
    for source_id, wanted in by_source.items():
        for clip in iter_clips(source_id, generation_config):
            if str(clip.clip_id) not in wanted:
                continue
            clip_id = str(clip.clip_id)
            frames = np.asarray(clip.frames, dtype=np.uint8)
            rows_by_method = groups[clip_id]
            digest = hashlib.sha256(frames.tobytes()).hexdigest()
            first_record = next(iter(rows_by_method.values()))
            expected_hash = first_record.get("pixels_sha256", first_record.get("frames_sha256"))
            if expected_hash is not None and digest != expected_hash:
                raise ValueError(f"Regenerated frames differ from run for {clip_id}")
            # Filenames derive from a digest, never from unchecked identifiers.
            safe_key = hashlib.sha256(clip_id.encode()).hexdigest()[:16]
            height, width = frames.shape[1:3]
            columns = min(12, len(frames))
            grid_rows = math.ceil(len(frames) / columns)
            sprite = Image.new("RGB", (columns * width, grid_rows * height))
            for index, frame in enumerate(frames):
                sprite.paste(Image.fromarray(frame), ((index % columns) * width, (index // columns) * height))
            sprite_name = f"{safe_key}-frames.png"
            sprite.save(assets / sprite_name)
            indices = {0}
            for row in rows_by_method.values():
                indices.update(int(index) for index in row["selected_indices"])
            annotation = clip.annotation
            if annotation.get("start_frame") is not None:
                indices.add(int(annotation["start_frame"]))
            frame_urls = {}
            for index in sorted(indices):
                if 0 <= index < len(frames):
                    name = f"{safe_key}-{index:03d}.png"
                    Image.fromarray(frames[index]).save(assets / name)
                    frame_urls[str(index)] = f"assets/{name}"
            clips_out.append({"clip_id": clip_id, "source_id": source_id, "fps": fps,
                              "n_frames": len(frames), "width": width, "height": height,
                              "annotation": annotation, "brief": clip.brief,
                              "reason": reasons[clip_id], "methods": rows_by_method,
                              "sprite_url": f"assets/{sprite_name}", "sprite_columns": columns,
                              "frames_sha256": digest, "frame_urls": frame_urls})
    found = {clip["clip_id"] for clip in clips_out}
    if found != set(reasons):
        raise ValueError(f"Generation config could not reproduce selected clips: {set(reasons) - found}")
    clips_out.sort(key=lambda clip: [key for key, _ in selected].index(clip["clip_id"]))
    summary_path = result_dir / "summary.json"
    run_summary = json.loads(summary_path.read_text()) if summary_path.is_file() else None
    summary = _summarize(rows)
    if run_summary is not None and str(budget) in run_summary.get("budgets", {}):
        budget_summary = run_summary["budgets"][str(budget)]
        intervals = budget_summary.get("uncertainty", {}).get("method_intervals", {})
        summary = []
        for method, item in budget_summary["methods"].items():
            summary.append({"method": method, "n_clips": item["n"],
                            "recall": item["recall"], "false_approval_rate": item["false_approval_rate"],
                            "false_positive_rate": item["false_alarm_rate"],
                            "median_pipeline_ms": item["latency_median_ms"],
                            "recall_ci95": intervals.get(method, {}).get("recall")})
    payload = {"schema_version": 1, "mode": "replay", "synthetic": True,
               "human_audit": "pending", "budget": budget,
               "source_predictions": source_path.name,
               "result_directory": result_dir.name,
               "selection_note": "Post-run illustrative cases; aggregate metrics use all completed rows, not this gallery.",
               "cost_note": "CPU pipeline = prepass + selection + verification; excludes generation. See run artifacts for full accounting.",
               "summary_source": "summary.json" if run_summary is not None else source_path.name,
               "hypothesis_supported": run_summary.get("hypothesis_supported") if run_summary else None,
               "summary": summary, "clips": clips_out}
    serialized = json.dumps(payload, indent=2, allow_nan=False)
    (output_dir / "data.json").write_text(serialized + "\n")
    # External local script permits file:// replay without a local web server.
    (output_dir / "data.js").write_text("window.BRIEFGUARD_DATA = " + serialized + ";\n")
    with (output_dir / "human_review.csv").open("w", newline="") as handle:
        fields = ["clip_id", "generator_type", "expected_truth", "generated_start_frame",
                  "generated_end_frame", "human_decision", "human_start_frame",
                  "human_end_frame", "reviewer", "notes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for clip in clips_out:
            annotation = clip["annotation"]
            writer.writerow({"clip_id": clip["clip_id"],
                             "generator_type": annotation.get("violation_type") or "compliant",
                             "expected_truth": annotation.get("violated"),
                             "generated_start_frame": annotation.get("start_frame"),
                             "generated_end_frame": annotation.get("end_frame")})
    return {"output_dir": str(output_dir), "clips": len(clips_out), "budget": budget,
            "source_predictions": str(source_path)}

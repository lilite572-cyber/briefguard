"""Validate completed CPU-study exports before reporting or comparing them.

These checks detect incomplete or inconsistent local artifacts. They are not
signatures or authentication against someone able to rewrite all local files.
The original frozen runner and analytical code are intentionally unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

from .data import MOTIONS, VIOLATION_TYPES
from .metrics import summarize
from .runner import digest, read_rows, validate_config


def validate_completed_run(directory: Path, config: dict | None = None) -> tuple[dict, list[dict]]:
    """Return metadata/rows only when the complete expected evidence is present."""
    directory = Path(directory)
    try:
        return _validate(directory, config)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError(f"Malformed run evidence in {directory.name}: {type(exc).__name__}") from exc


def validate_saved_summary(directory: Path, rows: list[dict], config: dict) -> None:
    """Reject a stale summary without modifying the saved research evidence."""
    saved = json.loads((Path(directory) / "summary.json").read_text())
    if saved != summarize(rows, config):
        raise ValueError("Saved summary differs from validated prediction rows; rebuild the report explicitly")


def _validate(directory, config):
    meta = json.loads((directory / "metadata.json").read_text())
    identity = meta["identity"]
    actual_config = identity["config"]
    validate_config(actual_config)
    if config is not None and actual_config != config:
        raise ValueError("Run configuration differs from requested configuration")
    if meta.get("complete") is not True or meta.get("errors") != 0:
        raise ValueError("Run is incomplete or has unresolved errors")
    run_id = digest(identity)[:16]
    if meta["run_id"] != run_id:
        raise ValueError("Run identity digest mismatch")
    sources, split = identity["source_ids"], identity["split"]
    if (not isinstance(sources, list) or not sources or len(set(sources)) != len(sources)
            or any(type(s) is not int or s < 0 for s in sources) or split not in ("pilot", "dev", "test")):
        raise ValueError("Invalid source inventory or split")
    variants = [("clean", 0)] + [(kind, duration) for kind in VIOLATION_TYPES
                                 for duration in actual_config["durations"]]
    expected_clips = {f"s{source:06d}-{motion}-{kind}-{duration}": source
                      for source in sources for motion in MOTIONS for kind, duration in variants}
    manifest = read_rows(directory / "manifest.jsonl")
    by_clip = {item["clip_id"]: item for item in manifest}
    if len(by_clip) != len(manifest) or set(by_clip) != set(expected_clips):
        raise ValueError("Manifest does not cover each expected source/clip exactly once")
    for clip_id, item in by_clip.items():
        if item["source_id"] != expected_clips[clip_id] or item["split"] != split:
            raise ValueError("Manifest source or split mismatch")
    rows = read_rows(directory / "predictions.jsonl")
    pairs = {(method, budget) for method in actual_config["methods"] for budget in actual_config["budgets"]}
    expected_count = len(expected_clips) * len(pairs)
    if len(rows) != expected_count or meta.get("rows") != expected_count:
        raise ValueError("Prediction count differs from complete method/budget matrix")
    error_path = directory / "errors.jsonl"
    if error_path.exists() and read_rows(error_path):
        raise ValueError("Completed run has nonempty error evidence")
    seen = set()
    for row in rows:
        clip_id, method, budget = row["clip_id"], row["method"], row["budget"]
        unit = (clip_id, method, budget)
        if unit in seen or clip_id not in by_clip or (method, budget) not in pairs:
            raise ValueError("Duplicate or unexpected clip/method/budget unit")
        seen.add(unit)
        item = by_clip[clip_id]
        brief_hash = digest(row["brief"])
        if (row["run_id"] != run_id or row["split"] != split or row["source_id"] != item["source_id"]
                or row["pixels_sha256"] != item["pixels_sha256"] or row["annotation"] != item["annotation"]
                or brief_hash != item["brief_sha256"]):
            raise ValueError("Prediction identity, annotation, pixels or brief differs from manifest")
        if row["unit_id"] != digest([run_id, clip_id, row["pixels_sha256"], brief_hash, method, budget]):
            raise ValueError("Prediction unit digest mismatch")
        indices = row["selected_indices"]
        if (not isinstance(indices, list) or len(indices) != budget or len(set(indices)) != budget
                or any(type(i) is not int or not 0 <= i < actual_config["n_frames"] for i in indices)):
            raise ValueError("Selection does not match the exact unique frame budget")
        annotation = row["annotation"]
        hit = any(annotation["start_frame"] <= i < annotation["end_frame"] for i in indices) if annotation["violated"] else None
        if row["sampling_hit"] is not hit:
            raise ValueError("Sampling coverage disagrees with the event interval")
        prediction = row["prediction"]
        if prediction["violated"] is not None and type(prediction["violated"]) is not bool:
            raise ValueError("Prediction must contain a boolean or unknown violation label")
        expected_status = "indeterminate" if prediction["violated"] is None else "fail" if prediction["violated"] is True else "pass"
        if prediction["status"] != expected_status or "error" in prediction:
            raise ValueError("Prediction status is inconsistent or records an unresolved error")
    return meta, rows

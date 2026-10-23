"""Auditable experiment execution, immutable configuration and atomic resume."""
from __future__ import annotations

import hashlib
import gzip
import json
import math
import os
import platform
import resource
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import __version__ as pillow_version

from .data import iter_clips
from .metrics import score, summarize, write_report
from .sampling import extract_features, select_frames
from .verifier import MODEL_VERSION, verify

ROOT = Path(__file__).resolve().parents[1]
CORE_FILES = ["briefguard/data.py", "briefguard/verifier.py", "briefguard/sampling.py",
              "briefguard/runner.py", "briefguard/metrics.py", "docs/protocol.md"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(tmp, path)


def source_fingerprint():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in CORE_FILES}


def validate_config(config):
    for field in ("n_frames", "width", "height", "fps", "bootstrap_resamples", "test_min_sources", "test_max_sources"):
        if not isinstance(config[field], int) or isinstance(config[field], bool) or config[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if config["api_spend_limit_usd"] != 0:
        raise ValueError("Local study does not authorize external API spending")
    if len(set(config["methods"])) != len(config["methods"]) or set(config["methods"]) != {"uniform", "change", "adaptive"}:
        raise ValueError("Exactly three prespecified methods required")
    if (not config["budgets"] or len(set(config["budgets"])) != len(config["budgets"])
            or any(not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= config["n_frames"] for k in config["budgets"])):
        raise ValueError("Unique positive budgets within frame count required")
    if config["primary_budget"] not in config["budgets"]:
        raise ValueError("Primary budget absent")
    if config["test_min_sources"] > config["test_max_sources"]:
        raise ValueError("Invalid source caps")
    ranges = [set(range(config[k][0], config[k][1] + 1)) for k in ("pilot_sources", "dev_sources")]
    ranges.append(set(range(config["test_start"], config["test_start"] + config["test_max_sources"])))
    if any(not r for r in ranges) or any(ranges[i] & ranges[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("Source splits must be nonempty and disjoint")


def read_rows(path):
    path = Path(path)
    if not path.exists() and path.with_suffix(path.suffix + ".gz").exists():
        path = path.with_suffix(path.suffix + ".gz")
    content = gzip.decompress(path.read_bytes()).decode() if path.suffix == ".gz" else path.read_text()
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def freeze(config, pilot_dir: Path, path: Path):
    validate_config(config)
    if path.exists():
        raise ValueError("Freeze exists; do not overwrite after seeing test data. Create an explicit amendment.")
    meta = json.loads((pilot_dir / "metadata.json").read_text())
    if meta["identity"]["split"] != "pilot" or meta["identity"]["config"] != config:
        raise ValueError("Pilot must use identical config")
    if meta["identity"]["core_files"] != source_fingerprint() or not meta.get("complete"):
        raise ValueError("Pilot incomplete or source changed; rerun pilot before freezing")
    rows = read_rows(pilot_dir / "predictions.jsonl")
    sd = {}
    per_source = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["budget"] == config["primary_budget"]:
            per_source[row["source_id"]][row["method"]].append(row)
    for baseline in ("uniform", "change"):
        differences = [score(g["adaptive"])["recall"] - score(g[baseline])["recall"] for g in per_source.values()]
        sd[baseline] = float(np.std(differences, ddof=1))
    raw_n = max(math.ceil((1.96 * s / config["target_ci_halfwidth"]) ** 2) for s in sd.values())
    n = min(config["test_max_sources"], max(config["test_min_sources"], raw_n))
    record = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "config": config,
              "core_files": source_fingerprint(), "pilot_run_id": meta["run_id"],
              "pilot_predictions_sha256": hashlib.sha256("".join(canonical(r) + "\n" for r in rows).encode()).hexdigest(),
              "planning": {"paired_source_sd": sd, "unclipped_n": raw_n, "chosen_n": n,
                           "target_halfwidth": config["target_ci_halfwidth"], "method": "approximate normal precision, clipped runtime cap"},
              "test_source_ids": list(range(config["test_start"], config["test_start"] + n)),
              "test_results_seen": False}
    record["freeze_id"] = digest(record)
    atomic_json(path, record)
    return record


def run(config, split, output: Path, frozen_path: Path | None = None):
    validate_config(config)
    core = source_fingerprint()
    freeze_id = None
    if split == "test":
        if frozen_path is None:
            raise ValueError("Test requires a precommitted freeze")
        frozen = json.loads(frozen_path.read_text())
        if frozen["config"] != config or frozen["core_files"] != core:
            raise ValueError("Frozen config/core source drift; test refused")
        freeze_id = frozen.pop("freeze_id")
        if digest(frozen) != freeze_id:
            raise ValueError("Freeze integrity check failed")
        sources = frozen["test_source_ids"]
    elif split in ("pilot", "dev"):
        start, end = config[split + "_sources"]
        sources = list(range(start, end + 1))
    else:
        raise ValueError("Unknown split")
    identity = {"config": config, "split": split, "source_ids": sources, "core_files": core,
                "model_version": MODEL_VERSION, "numpy": np.__version__, "pillow": pillow_version,
                "freeze_id": freeze_id}
    run_id = digest(identity)[:16]
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "metadata.json"
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text())
        if previous["identity"] != identity:
            raise ValueError("Output contains a different run; choose a new directory")
        started_at = previous["started_at_utc"]
    else:
        started_at = datetime.now(timezone.utc).isoformat()
    metadata = {"run_id": run_id, "identity": identity, "started_at_utc": started_at,
                "host": {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version},
                "complete": False, "mode": "actual_local_pixel_experiment", "human_audit": "pending"}
    atomic_json(metadata_path, metadata)
    started = time.perf_counter()
    rows, errors = [], []
    cache_hits, fresh = 0, 0
    source_manifest = []
    cache_dir = output / "cache"
    cache_dir.mkdir(exist_ok=True)
    # Exported rows also allow resume in a fresh checkout where local cache is ignored.
    saved_rows = {}
    if (output / "predictions.jsonl").exists() or (output / "predictions.jsonl.gz").exists():
        for row in read_rows(output / "predictions.jsonl"):
            if row["run_id"] == run_id:
                saved_rows[row["unit_id"]] = row
    for source_id in sources:
        iterator = iter_clips(source_id, config)
        while True:
            generated_at = time.perf_counter()
            try:
                clip = next(iterator)
            except StopIteration:
                break
            generation_s = time.perf_counter() - generated_at
            pixel_hash = hashlib.sha256(clip.frames.tobytes()).hexdigest()
            source_manifest.append({"source_id": source_id, "clip_id": clip.clip_id, "split": split,
                                    "pixels_sha256": pixel_hash, "annotation": clip.annotation,
                                    "brief_sha256": digest(clip.brief)})
            features_by_method = {}
            # Cycle method order by source to reduce fixed-order timing bias.
            offset = source_id % len(config["methods"])
            methods = config["methods"][offset:] + config["methods"][:offset]
            for method in methods:
                for budget in config["budgets"]:
                    unit_id = digest([run_id, clip.clip_id, pixel_hash, digest(clip.brief), method, budget])
                    cache_file = cache_dir / (unit_id + ".json")
                    cached = saved_rows.get(unit_id)
                    if cached is None and cache_file.exists():
                        cached = json.loads(cache_file.read_text())
                    if cached is not None:
                        if cached.get("unit_id") != unit_id or cached.get("run_id") != run_id:
                            raise ValueError("Cache identity mismatch")
                        rows.append(cached)
                        cache_hits += 1
                        continue
                    try:
                        if method not in features_by_method:
                            pre_start = time.perf_counter()
                            features = None if method == "uniform" else extract_features(
                                clip.frames, {**config["sampling"], "feature_mode": "global" if method == "change" else "all"})
                            pre_s = 0.0 if features is None else time.perf_counter() - pre_start
                            features_by_method[method] = (features, pre_s)
                        features, pre_s = features_by_method[method]
                        selected_at = time.perf_counter()
                        indices = select_frames(method, len(clip.frames), budget, features, config["sampling"])
                        selection_s = time.perf_counter() - selected_at
                        verify_at = time.perf_counter()
                        prediction = verify(clip.frames[indices], indices, clip.brief)
                        verification_s = time.perf_counter() - verify_at
                        if "error" in prediction:
                            raise ValueError("Verifier input error: " + prediction["error"])
                        annotation = clip.annotation
                        hit = any(annotation["start_frame"] <= i < annotation["end_frame"] for i in indices) if annotation["violated"] else None
                        fmeta = features["metadata"] if features else {}
                        row = {"run_id": run_id, "unit_id": unit_id, "clip_id": clip.clip_id, "source_id": source_id,
                               "split": split, "budget": budget, "method": method, "annotation": annotation,
                               "pixels_sha256": pixel_hash, "brief": clip.brief, "selected_indices": indices,
                               "prediction": prediction, "sampling_hit": hit,
                               "timing": {"generation_s": generation_s, "prepass_s": pre_s,
                                          "selection_s": selection_s, "verification_s": verification_s},
                               "resources": {"prepass_frames": fmeta.get("frames_examined", 0),
                                             "prepass_source_pixels": fmeta.get("source_pixels_read", 0),
                                             "prepass_low_res_pixels": fmeta.get("low_resolution_pixels", 0),
                                             "checked_frames": len(indices), "checked_pixels": len(indices) * config["height"] * config["width"],
                                             "verifier_calls": 1, "api_calls": 0, "api_cost_usd": 0.0,
                                             "feature_reuse_across_budgets": True, "full_prepass_charged": True}}
                        atomic_json(cache_file, row)
                        rows.append(row)
                        fresh += 1
                    except Exception as exc:
                        errors.append({"source_id": source_id, "clip_id": clip.clip_id, "method": method,
                                       "budget": budget, "error_type": type(exc).__name__, "error": str(exc)})
        print(f"{split}: source {source_id} complete; fresh={fresh}, reused={cache_hits}", flush=True)
    rows.sort(key=lambda r: (r["source_id"], r["clip_id"], r["budget"], r["method"]))
    for name, records in (("predictions.jsonl", rows), ("manifest.jsonl", source_manifest), ("errors.jsonl", errors)):
        temp = output / (name + ".tmp")
        temp.write_text("".join(canonical(r) + "\n" for r in records))
        os.replace(temp, output / name)
        if name != "errors.jsonl":
            (output / (name + ".gz")).write_bytes(gzip.compress((output / name).read_bytes(), mtime=0))
    metadata.update({"complete": not errors, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                     "invocation_wall_s": time.perf_counter() - started, "fresh_units": fresh,
                     "reused_units": cache_hits, "rows": len(rows), "errors": len(errors),
                     "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                     "api_spend_usd": 0.0})
    atomic_json(metadata_path, metadata)
    if errors:
        raise RuntimeError(f"{len(errors)} units failed; inspect errors.jsonl and resume after fixing the cause")
    summary = summarize(rows, config)
    write_report(summary, output)
    return metadata

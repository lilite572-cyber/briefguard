"""Separately gated exploratory pilot; never imported by the frozen CPU runner."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import time

import numpy as np
from PIL import Image

from .data import iter_clips
from .sampling import extract_features, select_frames
from .video import load_video
from .vlm import PilotConfig, PilotError, ResponsesPilot, _atomic_result

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/vlm_pilot_v1.json"
LOCK_FILES = ("configs/vlm_pilot_v1.json", "docs/natural_video_pilot.md",
              "briefguard/pilot.py", "briefguard/vlm.py", "briefguard/video.py",
              "briefguard/sampling.py", "briefguard/data.py", "configs/study.json")
FIELDS = ["case_id", "label", "start_frame", "end_frame", "reviewer", "notes"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def code_hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in LOCK_FILES}


def _write(path, value):
    _atomic_result(path, value)


def _synthetic(config):
    study = json.loads((ROOT / "configs/study.json").read_text())
    for clip_id in config["synthetic_clip_ids"]:
        seed = int(clip_id.split("-")[0][1:])
        clip = next(c for c in iter_clips(seed, study) if c.clip_id == clip_id)
        requirements = {f"rule_{i}": value for i, value in enumerate(clip.brief["requirements"])}
        yield {"source_id": f"synthetic-{seed}", "origin": "synthetic", "clip_id": clip_id,
               "frames": clip.frames, "brief": clip.brief, "requirements": requirements,
               "durations": [1 / clip.brief["fps"]] * len(clip.frames),
               "annotation": clip.annotation}


def _natural(path, config):
    source = config["natural_source"]
    started = time.perf_counter()
    video = load_video(path, width=128, height=128, max_frames=600,
                       max_pixels=4096 * 4096, max_bytes=128 * 1024 * 1024)
    decode_seconds = time.perf_counter() - started
    n = len(video.frames)
    if n < source["minimum_frames"]:
        raise ValueError("Natural source has too few frames for the fixed protocol")
    requirements = {"earth_visible": "The Earth must remain visible in every supplied frame.",
                    "no_magenta_overlay": "No opaque bright magenta rectangle may overlay the scene."}
    for variant in source["variants"]:
        frames = video.frames.copy()
        start = end = None
        if variant == "blackout":
            start, end = n // 3, n // 3 + 2
            frames[start:end] = 0
        elif variant == "magenta_patch":
            start, end = n // 2, n // 2 + 6
            frames[start:end, :64, 64:] = [255, 0, 255]
        yield {"source_id": source["source_id"], "origin": "natural_source_injected",
               "clip_id": source["source_id"] + "-" + variant, "frames": frames,
               "brief": {"subject": "Earth photographed by EPIC", "requirements": list(requirements.values())},
               "requirements": requirements, "durations": video.durations_seconds,
               "decode_seconds": decode_seconds, "annotation": {"violated": variant != "clean",
               "start_frame": start, "end_frame": end, "human_audit": "pending"}}


def prepare(directory, natural_input=None):
    """Freeze source identity before selection. No network or model is used."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "input_freeze.json").exists():
        raise ValueError("Existing preparation is immutable; preserve it and use a new directory before spending")
    config = json.loads(CONFIG.read_text())
    clips = list(_synthetic(config))
    natural_hash = None
    if natural_input:
        natural_input = Path(natural_input)
        if natural_input.suffix.lower() != ".gif":
            raise ValueError("This protocol requires the original NASA GIF")
        if natural_input.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("NASA GIF exceeds 16 MiB source limit")
        natural_hash = digest(natural_input.read_bytes())
        clips.extend(_natural(natural_input, config))
    # Stable opaque order hides method outputs and corruption names from reviewer UI.
    clips.sort(key=lambda c: digest(c["clip_id"].encode()))
    identities = []
    review = directory / "review"
    review.mkdir(exist_ok=True)
    for i, clip in enumerate(clips):
        clip["case_id"] = f"case-{i + 1:02d}"
        case = review / clip["case_id"]
        case.mkdir(exist_ok=True)
        frames_path = directory / (clip["case_id"] + ".npy")
        np.save(frames_path, clip["frames"], allow_pickle=False)
        for index, frame in enumerate(clip["frames"]):
            Image.fromarray(frame).save(case / f"{index:04d}.png")
        previews = [Image.fromarray(frame) for frame in clip["frames"]]
        previews[0].save(case / "preview.gif", save_all=True, append_images=previews[1:],
                         duration=[max(10, round(d * 1000)) for d in clip["durations"]], loop=0, optimize=False)
        identities.append({"case_id": clip["case_id"], "pixels_sha256": digest(clip["frames"].tobytes()),
                           "npy_sha256": digest(frames_path.read_bytes()), "shape": list(clip["frames"].shape)})
    lock = {"study_id": config["study_id"], "code_hashes": code_hashes(),
            "natural_source_sha256": natural_hash, "cases": identities}
    _write(directory / "input_freeze.json", lock)
    lock_hash = digest((directory / "input_freeze.json").read_bytes())
    rows, cases = [], []
    sampling = json.loads((ROOT / "configs/study.json").read_text())["sampling"]
    for clip in clips:
        frames = clip.pop("frames")
        cases.append(clip)
        for method in config["methods"]:
            started = time.perf_counter()
            features = None if method == "uniform" else extract_features(frames, {**sampling, "feature_mode": "global" if method == "change" else "all"})
            prepass = time.perf_counter() - started if method != "uniform" else 0.0
            started = time.perf_counter()
            indices = select_frames(method, len(frames), config["frame_budget"], features, sampling)
            selection_seconds = time.perf_counter() - started
            ann = clip["annotation"]
            rows.append({"case_id": clip["case_id"], "method": method, "selected_indices": indices,
                         "prepass_seconds": prepass, "selection_seconds": selection_seconds,
                         "preprocessed_frames": len(frames) if features else 0,
                         "preprocessed_pixels": features["metadata"]["source_pixels_read"] if features else 0,
                         "injected_event_captured": (any(ann["start_frame"] <= k < ann["end_frame"] for k in indices) if ann["violated"] else None)})
    plan = {"input_freeze_sha256": lock_hash, "config": config, "cases": cases, "jobs": rows,
            "complete_data": natural_hash is not None, "human_review": "pending", "live_requests": 0,
            "expected_http_attempts_max": len(rows) * (config["retries"] + 1),
            "natural_data_status": "prepared_not_human_verified" if natural_hash else "not_downloaded",
            "estimated_full_plan_usd": config["max_requests"] * (config["planned_input_tokens_per_attempt"] * config["input_usd_per_million"] + config["max_output_tokens"] * config["output_usd_per_million"]) / 1e6}
    _write(directory / "plan.json", plan)
    (directory / "plan.sha256").write_text(digest((directory / "plan.json").read_bytes()) + "\n")
    _write(directory / "source_confirmation.json", {"source_sha256": natural_hash, "reviewer": "", "confirmed_exact_nasa_source": False})
    with (directory / "human_review.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({"case_id": c["case_id"]} for c in cases)
    page = ["<!doctype html><html lang=en><meta charset=utf-8><title>Blind pilot review</title><h1>Pilot human review</h1><p>Use the full preview and numbered PNG frames. Fill human_review.csv with pass, fail or indeterminate; a fail needs a half-open frame interval. These labels must be your own.</p>"]
    for case in cases:
        cid = case["case_id"]
        starts = np.cumsum([0.0] + case["durations"][:-1]).tolist()
        frame_links = " ".join(f'<a href="{cid}/{i:04d}.png">{i} ({starts[i]:.3f}s, duration {duration:.3f}s)</a>' for i, duration in enumerate(case["durations"]))
        page.append(f'<section><h2>{cid}</h2><p>{html.escape(" ".join(case["requirements"].values()))}</p><details><summary>Shared brief and reference values</summary><pre>{html.escape(json.dumps(case["brief"], indent=2))}</pre></details><img src="{cid}/preview.gif" alt="{cid} preview"><details><summary>All numbered frames</summary>{frame_links}</details></section>')
    (review / "index.html").write_text("\n".join(page) + "</html>")
    return plan


def validate_preparation(directory):
    directory = Path(directory)
    lock = json.loads((directory / "input_freeze.json").read_text())
    plan = json.loads((directory / "plan.json").read_text())
    if digest((directory / "plan.json").read_bytes()) != (directory / "plan.sha256").read_text().strip():
        raise ValueError("Prepared plan drift")
    if plan["config"] != json.loads(CONFIG.read_text()):
        raise ValueError("Prepared budget/model configuration differs from approved protocol")
    if lock["code_hashes"] != code_hashes() or plan["input_freeze_sha256"] != digest((directory / "input_freeze.json").read_bytes()):
        raise ValueError("Pilot code/protocol/input freeze drift; do not reinterpret old outputs")
    for case in lock["cases"]:
        if digest((directory / (case["case_id"] + ".npy")).read_bytes()) != case["npy_sha256"]:
            raise ValueError("Prepared pixel file drift")
    return plan


def human_labels(directory, plan):
    with (Path(directory) / "human_review.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError("Human CSV columns differ from the prepared template")
        rows = list(reader)
    expected = {c["case_id"]: len(c["durations"]) for c in plan["cases"]}
    labels = {}
    for row in rows:
        if set(row) != set(FIELDS) or any(not isinstance(value, str) for value in row.values()):
            raise ValueError("Human CSV row is malformed")
        cid = row["case_id"]
        if cid not in expected or cid in labels or row["label"] not in ("pass", "fail", "indeterminate") or not row["reviewer"].strip():
            raise ValueError("Human labels missing, duplicate or invalid; no request sent")
        start = end = None
        if row["label"] == "fail":
            start, end = int(row["start_frame"]), int(row["end_frame"])
            if not 0 <= start < end <= expected[cid]:
                raise ValueError("Invalid human event interval")
        elif row["start_frame"].strip() or row["end_frame"].strip():
            raise ValueError("Pass/indeterminate labels must not supply an event interval")
        labels[cid] = {"label": row["label"], "start_frame": start, "end_frame": end}
    if set(labels) != set(expected):
        raise ValueError("Every pilot case needs a human decision")
    return labels


def summarize(plan, outcomes, labels):
    groups = {}
    cases = {c["case_id"]: c for c in plan["cases"]}
    for outcome in outcomes:
        key = cases[outcome["case_id"]]["origin"] + "/" + outcome["method"]
        group = groups.setdefault(key, {"cases": 0, "positive": 0, "negative": 0, "unknown": 0, "detected": 0,
                                      "false_approved": 0, "false_alarms": 0, "indeterminate": 0, "operational_errors": 0,
                                      "event_captured": 0, "captured_but_missed": 0})
        group["cases"] += 1
        truth = labels[outcome["case_id"]]
        prediction = outcome["result"]["status"]
        group["indeterminate"] += prediction == "indeterminate"
        group["operational_errors"] += "error" in outcome
        if truth["label"] == "indeterminate":
            group["unknown"] += 1
            continue
        if truth["label"] == "fail":
            group["positive"] += 1
            group["detected"] += prediction == "fail"
            group["false_approved"] += prediction == "pass"
            captured = any(truth["start_frame"] <= i < truth["end_frame"] for i in outcome["selected_indices"])
            group["event_captured"] += captured
            group["captured_but_missed"] += captured and prediction != "fail"
        else:
            group["negative"] += 1
            group["false_alarms"] += prediction == "fail"
    for group in groups.values():
        group["recall"] = group["detected"] / group["positive"] if group["positive"] else None
        group["false_approval_rate"] = group["false_approved"] / group["positive"] if group["positive"] else None
        group["false_alarm_rate"] = group["false_alarms"] / group["negative"] if group["negative"] else None
    return {"mode": "exploratory_not_confirmatory", "groups": groups, "confidence_intervals": "not_estimated_too_few_sources"}


def run(directory, approved=False, *, transport=None):
    if approved is not True:
        raise ValueError("Separate approval of OpenAI / gpt-4.1-mini-2025-04-14 / USD 0.50 is required")
    directory = Path(directory)
    plan = validate_preparation(directory)
    if not plan["complete_data"]:
        raise ValueError("Natural source is missing; paid protocol is not ready")
    labels = human_labels(directory, plan)
    source_review = json.loads((directory / "source_confirmation.json").read_text())
    lock = json.loads((directory / "input_freeze.json").read_text())
    if (source_review.get("confirmed_exact_nasa_source") is not True or not isinstance(source_review.get("reviewer"), str)
            or not source_review["reviewer"].strip()
            or source_review.get("source_sha256") != lock["natural_source_sha256"]):
        raise ValueError("Human confirmation of the exact NASA source is required")
    identity = {"plan_sha256": digest((directory / "plan.json").read_bytes()),
                "labels_sha256": digest((directory / "human_review.csv").read_bytes()),
                "source_review_sha256": digest((directory / "source_confirmation.json").read_bytes())}
    identity_path = directory / "run_identity.json"
    if identity_path.exists() and json.loads(identity_path.read_text()) != identity:
        raise ValueError("Run inputs or human labels changed; preserve old outcomes")
    _write(identity_path, identity)
    cfg = json.loads(CONFIG.read_text())
    approved_contract = {"provider": "OpenAI Responses API", "model": "gpt-4.1-mini-2025-04-14",
                         "max_spend_usd": 0.5, "max_requests": 36, "reservation_usd": 0.01,
                         "max_output_tokens": 800, "retries": 1,
                         "input_usd_per_million": 0.4, "output_usd_per_million": 1.6}
    if any(cfg.get(key) != value for key, value in approved_contract.items()):
        raise ValueError("Configuration exceeds or differs from the explicit approval contract")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing; no outcomes or requests created")
    config = PilotConfig(**{key: cfg[key] for key in ("model", "max_requests", "max_spend_usd", "reservation_usd", "input_usd_per_million", "output_usd_per_million", "max_output_tokens", "retries")}, authorized=True)
    adapter = ResponsesPilot(config, directory / "api", transport=transport)
    cases = {c["case_id"]: c for c in plan["cases"]}
    outcomes = []
    output = directory / "outcomes"
    output.mkdir(exist_ok=True)
    for job in plan["jobs"]:
        target = output / (job["case_id"] + "-" + job["method"] + ".json")
        if target.exists():
            row = json.loads(target.read_text())
            if (row.get("run_identity") != identity or
                    any(row.get(key) != job[key] for key in ("case_id", "method", "selected_indices"))):
                raise ValueError("Saved logical outcome identity mismatch")
            outcomes.append(row)
            continue
        case = cases[job["case_id"]]
        frames = np.load(directory / (job["case_id"] + ".npy"), allow_pickle=False)
        started = time.perf_counter()
        row = {**job, "run_identity": identity}
        try:
            row["result"] = adapter.verify([Image.fromarray(frames[i]) for i in job["selected_indices"]], job["selected_indices"], case["requirements"], case["brief"])
            if row["result"].get("model_version") != cfg["model"]:
                row["unexpected_model_response"] = row["result"]
                raise PilotError("Returned model differs from the pinned snapshot; excluded from accuracy as operational indeterminate")
        except PilotError as exc:
            row.update(result={"status": "indeterminate", "evidence": []}, error=str(exc))
        row["verification_wall_seconds"] = time.perf_counter() - started
        _write(target, row)
        outcomes.append(row)
    summary = summarize(plan, outcomes, labels)
    ledger_path = directory / "api/ledger.jsonl"
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
    attempts = [entry for entry in ledger if "reservation_usd" in entry]
    costs = [entry["estimated_api_cost_usd"] for entry in ledger if entry.get("estimated_api_cost_usd") is not None]
    summary["api_accounting"] = {"attempts": len(attempts), "reserved_usd": sum(entry["reservation_usd"] for entry in attempts),
                                 "known_usage_cost_estimate_usd": sum(costs), "attempts_without_known_cost": len(attempts) - len(costs),
                                 "provider_billing_guarantee": False}
    summary["human_labels_sha256"] = digest((directory / "human_review.csv").read_bytes())
    summary["input_freeze_sha256"] = plan["input_freeze_sha256"]
    _write(directory / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--out", required=True)
    prep.add_argument("--natural-input")
    execute = sub.add_parser("run")
    execute.add_argument("--directory", required=True)
    execute.add_argument("--approve-openai-gpt41mini-usd050", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.out, args.natural_input)
            print(json.dumps({"cases": len(result["cases"]), "logical_checks": len(result["jobs"]), "complete_data": result["complete_data"], "live_requests": 0}, indent=2))
        else:
            print(json.dumps(run(args.directory, args.approve_openai_gpt41mini_usd050), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Pilot refused: {exc}\n")


if __name__ == "__main__":
    main()

"""Version-two NASA pilot amendment, preserving the version-one runtime verbatim.

Shared pure helpers are imported from the archived v1 module. Preparation,
validation and execution are versioned here because the selected protocol and
all dependency hashes form each immutable pilot identity. No model call occurs
while preparing; human labels/source confirmation and paid approval still gate run.
"""
from __future__ import annotations

import csv
import html
import json
import os
from pathlib import Path
import time

import numpy as np
from PIL import Image

from . import pilot as v1
from .pilot import digest, _write, _synthetic, human_labels, summarize, FIELDS
from .sampling import extract_features, select_frames
from .vlm import PilotConfig, PilotError, ResponsesPilot

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/vlm_pilot_v2.json"
LOCK_FILES = ("configs/vlm_pilot_v2.json", "docs/natural_video_pilot_v2.md",
              "briefguard/pilot_v2.py", "briefguard/pilot.py",
              "configs/vlm_pilot_v1.json", "docs/natural_video_pilot.md",
              "briefguard/vlm.py", "briefguard/video.py",
              "briefguard/sampling.py", "briefguard/data.py", "configs/study.json")


def code_hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in LOCK_FILES}


def _natural(path, config):
    source = config["natural_source"]
    if digest(Path(path).read_bytes()) != source["expected_sha256"]:
        raise ValueError("Source bytes differ from the pinned official NASA GIF; do not substitute another clip")
    for clip in v1._natural(path, config):
        if len(clip["frames"]) != source["expected_frames"]:
            raise ValueError("NASA display-frame count differs from protocol v2")
        yield clip


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
    plan = {"protocol_version": "v2", "input_freeze_sha256": lock_hash, "config": config, "cases": cases, "jobs": rows,
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
    if plan.get("protocol_version") != "v2" or plan["config"] != json.loads(CONFIG.read_text()):
        raise ValueError("Prepared budget/model configuration differs from approved protocol")
    if lock["code_hashes"] != code_hashes() or plan["input_freeze_sha256"] != digest((directory / "input_freeze.json").read_bytes()):
        raise ValueError("Pilot code/protocol/input freeze drift; do not reinterpret old outputs")
    for case in lock["cases"]:
        if digest((directory / (case["case_id"] + ".npy")).read_bytes()) != case["npy_sha256"]:
            raise ValueError("Prepared pixel file drift")
    return plan


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

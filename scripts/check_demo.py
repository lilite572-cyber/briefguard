"""Verify replay evidence and pixels; this is not browser/visual QA."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefguard.data import iter_clips
from briefguard.metrics import score
from briefguard.runner import read_rows


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_demo(demo: Path, run: Path, config: dict) -> dict:
    payload = json.loads((demo / "data.json").read_text())
    script = (demo / "data.js").read_text().strip()
    prefix = "window.BRIEFGUARD_DATA = "
    require(script.startswith(prefix) and script.endswith(";"), "Invalid data.js wrapper")
    require(json.loads(script[len(prefix):-1]) == payload, "data.js differs from data.json")
    require(payload["mode"] == "replay" and payload["synthetic"] is True, "Replay mode missing")
    meta = json.loads((run / "metadata.json").read_text())
    rows = read_rows(run / "predictions.jsonl")
    require(meta["complete"] is True and meta["rows"] == len(rows), "Incomplete source run")
    require(meta["identity"]["config"] == config, "Configuration differs from source run")
    by_unit = {(r["clip_id"], r["budget"], r["method"]): r for r in rows}
    require(len(by_unit) == len(rows), "Duplicate source units")
    budget = payload["budget"]
    source_summary = json.loads((run / "summary.json").read_text())
    require(payload["hypothesis_supported"] == source_summary["hypothesis_supported"],
            "Hypothesis conclusion differs from source")
    summaries = {s["method"]: s for s in payload["summary"]}
    require(set(summaries) == set(config["methods"]), "Missing summary methods")
    for method, shown in summaries.items():
        method_rows = [r for r in rows if r["budget"] == budget and r["method"] == method]
        actual = score(method_rows)
        recorded = source_summary["budgets"][str(budget)]["methods"][method]
        for view_key, result_key in (("n_clips", "n"), ("recall", "recall"),
                                     ("false_approval_rate", "false_approval_rate"),
                                     ("false_positive_rate", "false_alarm_rate")):
            require(shown[view_key] == recorded[result_key] == actual[result_key],
                    f"Incorrect summary: {method}/{view_key}")
        latency = float(np.median([sum(r["timing"][k] for k in
            ("prepass_s", "selection_s", "verification_s")) for r in method_rows]) * 1000)
        require(shown["median_pipeline_ms"] == recorded["latency_median_ms"] == latency,
                f"Incorrect latency summary: {method}")
        interval = source_summary["budgets"][str(budget)]["uncertainty"]["method_intervals"][method]["recall"]
        require(shown["recall_ci95"] == interval, f"Incorrect interval: {method}")

    references = set()

    def asset(url):
        require(isinstance(url, str) and re.fullmatch(r"assets/[A-Za-z0-9_.-]+\.png", url),
                "Unsafe asset URL")
        path = demo / url
        require(path.resolve().parent == (demo / "assets").resolve(), "Asset escapes directory")
        references.add(url)
        with Image.open(path) as image:
            require(image.mode == "RGB", f"Unexpected image mode: {url}")
            return np.asarray(image).copy()

    ids = [c["clip_id"] for c in payload["clips"]]
    require(len(ids) == len(set(ids)) and len(ids) > 0, "Empty or duplicate replay cases")
    regenerated = {}
    for source in sorted({c["source_id"] for c in payload["clips"]}):
        for clip in iter_clips(source, config):
            if clip.clip_id in ids:
                regenerated[clip.clip_id] = clip
    frame_count = 0
    method_count = 0
    for case in payload["clips"]:
        clip = regenerated[case["clip_id"]]
        frames = clip.frames
        n, height, width, _ = frames.shape
        require((case["n_frames"], case["height"], case["width"], case["fps"]) ==
                (n, height, width, config["fps"]), "Replay dimensions/timing differ")
        require(case["annotation"] == clip.annotation and case["brief"] == clip.brief,
                f"Brief/truth differ: {clip.clip_id}")
        require(case["frames_sha256"] == hashlib.sha256(frames.tobytes()).hexdigest(),
                f"Pixel hash differs: {clip.clip_id}")
        require(set(case["methods"]) == set(config["methods"]), "Missing case methods")
        selected = set()
        for method, row in case["methods"].items():
            require(row == by_unit[(clip.clip_id, budget, method)], "Replay evidence differs from source")
            require(len(row["selected_indices"]) == budget == len(set(row["selected_indices"])),
                    "Wrong selected frame budget")
            selected.update(row["selected_indices"])
            method_count += 1
        require(selected <= {int(i) for i in case["frame_urls"]}, "Selected frame asset absent")
        sprite = asset(case["sprite_url"])
        columns = case["sprite_columns"]
        require(sprite.shape == (math.ceil(n / columns) * height, columns * width, 3),
                "Sprite dimensions differ")
        for i, frame in enumerate(frames):
            y, x = (i // columns) * height, (i % columns) * width
            require(np.array_equal(sprite[y:y + height, x:x + width], frame),
                    f"Sprite frame differs: {clip.clip_id}/{i}")
            frame_count += 1
        for index, url in case["frame_urls"].items():
            require(0 <= int(index) < n and np.array_equal(asset(url), frames[int(index)]),
                    f"Frame image differs: {clip.clip_id}/{index}")
    actual_assets = {"assets/" + p.name for p in (demo / "assets").iterdir() if p.is_file()}
    require(actual_assets == references, "Missing or unreferenced assets in replay directory")
    return {"status": "passed", "kind": "static_evidence_and_pixel_check",
            "cases": len(ids), "method_cases": method_count,
            "image_assets": len(references), "sprite_frames": frame_count,
            "browser_visual_qa": "not_performed_by_this_script"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, default=Path("demo"))
    parser.add_argument("--run", type=Path, default=Path("results/test"))
    parser.add_argument("--config", type=Path, default=Path("configs/study.json"))
    args = parser.parse_args()
    try:
        result = check_demo(args.demo, args.run, json.loads(args.config.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Replay verification failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

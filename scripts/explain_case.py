"""Recompute one saved case and show where capture and recognition differ."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from briefguard.data import iter_clips
from briefguard.metrics import score
from briefguard.runner import read_rows
from briefguard.sampling import extract_features, select_frames
from briefguard.verifier import verify


def explain(run, clip_id, budget):
    metadata = json.loads((run / "metadata.json").read_text())
    if metadata.get("complete") is not True:
        raise ValueError("Choose a completed run")
    config = metadata["identity"]["config"]
    rows = read_rows(run / "predictions.jsonl")
    if len(rows) != metadata["rows"] or any(r["run_id"] != metadata["run_id"] for r in rows):
        raise ValueError("Saved rows do not match run metadata")
    chosen = [r for r in rows if r["clip_id"] == clip_id and r["budget"] == budget]
    if len(chosen) != len(config["methods"]) or {r["method"] for r in chosen} != set(config["methods"]):
        raise ValueError("Case must have one saved row per configured method")
    source_ids = {r["source_id"] for r in chosen}
    if len(source_ids) != 1:
        raise ValueError("Conflicting source identities")
    clip = next((c for c in iter_clips(source_ids.pop(), config) if c.clip_id == clip_id), None)
    if clip is None:
        raise ValueError("Generator could not reproduce this clip")
    pixels_sha256 = hashlib.sha256(clip.frames.tobytes()).hexdigest()
    methods = []
    for method in config["methods"]:
        saved = next(r for r in chosen if r["method"] == method)
        if saved["pixels_sha256"] != pixels_sha256 or saved["brief"] != clip.brief or saved["annotation"] != clip.annotation:
            raise ValueError("Regenerated clip differs from saved evidence")
        features = None if method == "uniform" else extract_features(
            clip.frames, {**config["sampling"], "feature_mode": "global" if method == "change" else "all"})
        indices = select_frames(method, len(clip.frames), budget, features, config["sampling"])
        prediction = verify(clip.frames[indices], indices, clip.brief)
        # Labels enter explanation only after selection and checking.
        annotation = clip.annotation
        captured = [i for i in indices if annotation["violated"] and annotation["start_frame"] <= i < annotation["end_frame"]]
        hit = bool(captured) if annotation["violated"] else None
        if indices != saved["selected_indices"] or prediction != saved["prediction"] or hit != saved["sampling_hit"]:
            raise ValueError(f"Recomputed evidence differs for {method}")
        metric = score([r for r in rows if r["method"] == method and r["budget"] == budget])
        methods.append({"method": method, "selected_indices": indices,
                        "event_frames_selected": captured, "decision": prediction["status"],
                        "false_approval": annotation["violated"] and prediction["status"] == "pass",
                        "evidence": prediction["evidence"],
                        "full_run_recall": {"detected": metric["tp"], "violating": metric["n_violating"],
                                            "ratio": metric["recall"]}})
    return {"run_id": metadata["run_id"], "clip_id": clip_id, "budget": budget,
            "pixels_sha256": pixels_sha256, "annotation": clip.annotation,
            "methods": methods, "exact_saved_evidence_match": True,
            "human_review_completed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "results/test")
    parser.add_argument("--clip", default="s010000-distractor-forbidden_patch-6")
    parser.add_argument("--budget", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(explain(args.run, args.clip, args.budget), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

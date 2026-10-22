"""Check deterministic evidence, deliberately excluding machine timing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefguard.runner import read_rows

left, right = map(Path, sys.argv[1:3])
keys = ("clip_id", "source_id", "split", "budget", "method", "annotation", "pixels_sha256",
        "brief", "selected_indices", "prediction", "sampling_hit", "resources")
a = read_rows(left / "predictions.jsonl")
b = read_rows(right / "predictions.jsonl")
assert len(a) == len(b), f"Different row counts: {len(a)} != {len(b)}"
for i, (x, y) in enumerate(zip(a, b)):
    assert {k: x[k] for k in keys} == {k: y[k] for k in keys}, f"Evidence mismatch at row {i}"
print(json.dumps({"matching_rows": len(a), "exact_evidence_match": True, "timing_compared": False}))

"""Check deterministic evidence, deliberately excluding machine timing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefguard.evidence import validate_completed_run

def compare(left, right):
    keys = ("clip_id", "source_id", "split", "budget", "method", "annotation", "pixels_sha256",
            "brief", "selected_indices", "prediction", "sampling_hit", "resources")
    left_meta, a = validate_completed_run(left)
    right_meta, b = validate_completed_run(right)
    if left_meta["identity"] != right_meta["identity"]:
        raise ValueError("Different run identities")
    if len(a) != len(b):
        raise ValueError(f"Different row counts: {len(a)} != {len(b)}")
    for i, (x, y) in enumerate(zip(a, b)):
        if {k: x[k] for k in keys} != {k: y[k] for k in keys}:
            raise ValueError(f"Evidence mismatch at row {i}")
    return {"matching_rows": len(a), "exact_evidence_match": True, "timing_compared": False}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/compare_runs.py LEFT_RUN RIGHT_RUN")
    try:
        print(json.dumps(compare(*map(Path, sys.argv[1:]))))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Comparison failed: {exc}") from None

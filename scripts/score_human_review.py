"""Validate actual human labels and describe agreement; never edits original truth."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from prepare_human_review import digest

KINDS = {"missing_product", "wrong_color", "label_corruption", "forbidden_patch"}


def score(key, submission):
    public = dict(key["public_payload"])
    package_id = public.pop("dataset_id")
    if digest(public) != package_id or key["dataset_id"] != package_id:
        raise ValueError("Evaluator key/public payload integrity mismatch")
    if submission.get("schema_version") != "human-labels-v1" or submission.get("dataset_id") != package_id:
        raise ValueError("Submission schema/package mismatch")
    if submission.get("reviewer_role") != "human" or submission.get("human_attestation") is not True or not isinstance(submission.get("reviewer_id"), str) or not submission["reviewer_id"].strip():
        raise ValueError("Actual human review and reviewer alias are required")
    expected = {c["case_id"]: c for c in key["cases"]}
    bounds = {c["case_id"]: c["frames"] for c in public["cases"]}
    labels = submission.get("labels")
    if not isinstance(labels, list) or len(labels) != len(expected) or any(not isinstance(r, dict) for r in labels):
        raise ValueError("All cases must be reviewed exactly once")
    ids = [r.get("case_id") for r in labels]
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ValueError("Missing, extra or duplicate case IDs")
    comparisons, groups = [], defaultdict(list)
    for row in labels:
        case = expected[row["case_id"]]
        decision, kind = row.get("decision"), row.get("violation_type")
        start, end, notes = row.get("start_frame"), row.get("end_frame"), row.get("notes")
        if decision not in {"violation", "compliant", "unknown"} or not isinstance(notes, str):
            raise ValueError("Invalid or blank human decision/notes")
        if decision == "violation":
            if kind not in KINDS or type(start) is not int or type(end) is not int or not 0 <= start < end <= bounds[row["case_id"]]:
                raise ValueError("Violation needs valid type and integer half-open interval")
        elif kind is not None or start is not None or end is not None:
            raise ValueError("Compliant/unknown labels must not specify event type or interval")
        if decision == "unknown" and not notes.strip():
            raise ValueError("Unknown labels require a reason")
        a = case["annotation"]
        known = decision != "unknown"
        presence_match = (decision == "violation") == a["violated"] if known else None
        exact_match = (presence_match and (decision == "compliant" or (kind == a["violation_type"] and start == a["start_frame"] and end == a["end_frame"]))) if known else None
        result = {"case_id": row["case_id"], "source_id": case["source_id"], "decision": decision,
                  "presence_agrees_with_generator": presence_match, "exact_type_interval_agrees": exact_match}
        comparisons.append(result)
        groups[case["source_id"]].append(result)
    known = [r for r in comparisons if r["decision"] != "unknown"]
    return {"schema_version": "human-audit-summary-v1", "dataset_id": package_id,
        "reviewer_id": submission["reviewer_id"], "label_origin": "human_self_attested_not_independently_authenticated",
        "n_cases": len(comparisons), "n_source_groups": len(groups), "n_unknown": len(comparisons)-len(known),
        "presence_agreement_count": sum(r["presence_agrees_with_generator"] for r in known),
        "exact_agreement_count": sum(r["exact_type_interval_agrees"] for r in known), "known_denominator": len(known),
        "source_groups": {str(k): {"n_cases": len(v), "unknown": sum(r["decision"] == "unknown" for r in v),
                          "disagreements": sum(r["exact_type_interval_agrees"] is False for r in v)} for k,v in sorted(groups.items())},
        "comparisons": comparisons,
        "interpretation": "Descriptive stratified development audit only. No population accuracy, CI, method ranking, independent-expert claim or change to frozen ground truth."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--key", type=Path, default=Path("human_review/evaluator_key.json"))
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error("Output exists; preserve prior review evidence")
    try:
        raw = args.labels.read_bytes()
        result = score(json.loads(args.key.read_text()), json.loads(raw))
        result["submission_sha256"] = hashlib.sha256(raw).hexdigest()
        result["evaluator_key_sha256"] = hashlib.sha256(args.key.read_bytes()).hexdigest()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"comparisons", "source_groups"}}, indent=2))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Preflight and guarded execution for the immutable BriefGuard v2 pilot.

The guard adds a stop between HTTP attempts when prior usage/outcome is unknown.
It never resets the existing ledger and never modifies frozen pilot files.
--check-only reports readiness without writing files or sending any request.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefguard import pilot_v2
from briefguard.vlm import _atomic_result, _transport

RUNNER_PATH = Path(__file__).resolve()
APPROVED_CONTRACT = {
    "provider": "OpenAI Responses API", "model": "gpt-4.1-mini-2025-04-14",
    "max_spend_usd": 0.5, "max_requests": 36, "reservation_usd": 0.01,
    "max_output_tokens": 800, "retries": 1,
    "input_usd_per_million": 0.4, "output_usd_per_million": 1.6,
}


class GuardStop(RuntimeError):
    """Stop the whole pilot, not merely one logical job, before another send."""


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ledger(directory, *, already_locked=False):
    path = Path(directory) / "api/ledger.jsonl"
    if not path.exists():
        return []
    if path.stat().st_size > 2_000_000:
        raise ValueError("Pilot ledger exceeds its expected bounded size; review it")
    with path.open() as stream:
        # During the callback ResponsesPilot already holds LOCK_EX on this file.
        # Taking a second lock through another descriptor here would deadlock.
        if not already_locked:
            fcntl.flock(stream, fcntl.LOCK_SH)
        return [json.loads(line) for line in stream if line.strip()]


def ledger_problems(entries, *, exclude_attempt=None):
    """Allow reserved 429/5xx retries, but halt on unknown paid outcomes/usage."""
    attempts = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return ["Malformed ledger entry"]
        if "reservation_usd" in entry:
            number = entry.get("attempt")
            if type(number) is not int or number < 1 or number in attempts:
                return ["Malformed or duplicate ledger attempt"]
            attempts[number] = {"reservation": entry, "events": []}
        elif "attempt" in entry:
            number = entry["attempt"]
            if type(number) is not int or number not in attempts:
                return ["Ledger event has no matching reservation"]
            attempts[number]["events"].append(entry)
    problems = []
    for number, record in attempts.items():
        if number == exclude_attempt:
            continue
        events = record["events"]
        statuses = [entry["http_status"] for entry in events if "http_status" in entry]
        if any(entry.get("reservation_exceeded") is True for entry in events):
            problems.append(f"Attempt {number}: observed usage exceeded reservation")
        if any("error" in entry for entry in events):
            problems.append(f"Attempt {number}: transport/outcome unresolved")
            continue
        if len(statuses) != 1 or type(statuses[0]) is not int:
            problems.append(f"Attempt {number}: pending or malformed HTTP outcome")
            continue
        status = statuses[0]
        if status == 429 or 500 <= status < 600:
            continue  # Retry still consumes the existing adapter's bounded reservation.
        if status != 200:
            problems.append(f"Attempt {number}: HTTP {status} requires review before further requests")
            continue
        costs = [entry["estimated_api_cost_usd"] for entry in events if "estimated_api_cost_usd" in entry]
        if (len(costs) != 1 or type(costs[0]) not in (int, float)
                or not math.isfinite(costs[0]) or costs[0] < 0):
            problems.append(f"Attempt {number}: successful HTTP response has unknown or invalid usage cost")
    return problems


def _identity(directory):
    directory = Path(directory)
    return {
        "runner_sha256": _sha(RUNNER_PATH),
        "plan_sha256": _sha(directory / "plan.json"),
        "human_labels_sha256": _sha(directory / "human_review.csv"),
        "source_confirmation_sha256": _sha(directory / "source_confirmation.json"),
        "input_freeze_sha256": _sha(directory / "input_freeze.json"),
        "approval_contract": APPROVED_CONTRACT,
    }


def readiness(directory, *, require_key=False):
    """Read-only preflight. Human labels and credentials are never printed."""
    directory = Path(directory)
    problems = []
    plan = None
    try:
        plan = pilot_v2.validate_preparation(directory)
        if not plan["complete_data"]:
            problems.append("Natural source is missing")
        if any(plan["config"].get(key) != value for key, value in APPROVED_CONTRACT.items()):
            problems.append("Pilot configuration differs from the fixed approval contract")
        try:
            pilot_v2.human_labels(directory, plan)
        except (ValueError, OSError, KeyError, TypeError):
            problems.append("Human review CSV is incomplete or invalid")
        try:
            review = json.loads((directory / "source_confirmation.json").read_text())
            lock = json.loads((directory / "input_freeze.json").read_text())
            expected_source = plan["config"]["natural_source"]["expected_sha256"]
            if (review.get("confirmed_exact_nasa_source") is not True
                    or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                    or review.get("source_sha256") != expected_source
                    or lock["natural_source_sha256"] != expected_source):
                problems.append("Human confirmation of the pinned NASA source is incomplete")
        except (ValueError, OSError, KeyError, TypeError):
            problems.append("Source confirmation is missing or malformed")
        identity_path = directory / "guarded_execution_identity.json"
        if identity_path.exists() and json.loads(identity_path.read_text()) != _identity(directory):
            problems.append("Guarded execution identity changed; preserve existing evidence")
        problems.extend(ledger_problems(_ledger(directory)))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        problems.append("Preparation or execution evidence is invalid: " + str(exc))
    if require_key and not os.environ.get("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY is missing from the process environment")
    return {"status": "ready" if not problems else "blocked", "ready": not problems,
            "protocol": "v2", "check_only": True, "network_calls": 0,
            "credential_check": "required" if require_key else "deferred_to_execution",
            "logical_checks": len(plan["jobs"]) if plan is not None else None,
            "allocation_usd": 0.5, "reasons": problems}


def execute(directory, approved=False, *, transport=None):
    """Use the existing pilot/ledger; stop all work before an unsafe next HTTP."""
    directory = Path(directory)
    if approved is not True:
        return {"status": "blocked", "reasons": ["Explicit --approve-openai-gpt41mini-usd050 acknowledgement is required"], "network_calls": 0}
    check = readiness(directory, require_key=True)
    if not check["ready"]:
        return {**check, "check_only": False}
    with (directory / "guarded_execution.lock").open("a") as runner_lock:
        try:
            fcntl.flock(runner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "blocked", "reasons": ["Another guarded pilot is active"], "network_calls": 0}
        check = readiness(directory, require_key=True)
        if not check["ready"]:
            return {**check, "check_only": False}
        identity_path = directory / "guarded_execution_identity.json"
        if not identity_path.exists():
            _atomic_result(identity_path, _identity(directory))
        calls = 0
        def guarded_transport(payload, key, timeout):
            nonlocal calls
            entries = _ledger(directory, already_locked=True)
            reservations = [entry for entry in entries if "reservation_usd" in entry]
            if not reservations or reservations[-1].get("request_id") != hashlib.sha256(payload).hexdigest():
                raise GuardStop("Current request has no matching ledger reservation; no HTTP sent")
            current = reservations[-1]["attempt"]
            problems = ledger_problems(entries, exclude_attempt=current)
            if problems:
                # The current reservation remains intact. This receipt explains
                # why its HTTP was deliberately not sent; no ledger entry is erased.
                with (directory / "guarded_execution_events.jsonl").open("a") as log:
                    log.write(json.dumps({"event": "blocked_before_http", "attempt": current, "reasons": problems}) + "\n")
                    log.flush()
                    os.fsync(log.fileno())
                raise GuardStop("Further HTTP blocked: " + "; ".join(problems))
            calls += 1
            return (transport or _transport)(payload, key, timeout)
        try:
            summary = pilot_v2.run(directory, approved=True, transport=guarded_transport)
            remaining = ledger_problems(_ledger(directory))
            if remaining:
                result = {"status": "blocked", "reasons": remaining, "summary_written": True,
                          "network_calls": calls, "check_only": False}
            else:
                result = {"status": "completed", "reasons": [], "network_calls": calls,
                          "check_only": False, "api_accounting": summary["api_accounting"]}
        except (GuardStop, ValueError, OSError, KeyError, TypeError) as exc:
            result = {"status": "blocked", "reasons": [str(exc)], "network_calls": calls, "check_only": False}
        _atomic_result(directory / "guarded_execution_status.json", result)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "results/private-vlm-pilot-v2")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--approve-openai-gpt41mini-usd050", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = readiness(args.directory) if args.check_only else execute(args.directory, args.approve_openai_gpt41mini_usd050)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {"status": "blocked", "reasons": [str(exc)], "network_calls": 0}
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in ("ready", "completed") else 2


if __name__ == "__main__":
    raise SystemExit(main())

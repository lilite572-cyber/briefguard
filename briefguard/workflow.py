"""Prepare offline video reviews, inspect imports, or execute after explicit approval.

Preparation and import never use the network. The separate execute subcommand
requires a fixed provider/model/budget acknowledgement and a private API key.
This product workflow is separate from both frozen studies. A prepared request is
not a model result. Imported provider-shaped JSON is operator-supplied evidence,
not authenticated proof of a provider call or an independent accuracy experiment.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from PIL import Image

from .sampling import extract_features, select_frames
from .video import load_video
from .vlm import PROMPT, SCHEMA, PilotConfig, PilotError, ResponsesPilot, _atomic_result, _transport, _validate_result

DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
MAX_JSON = 4_000_000
API_DIRECTORY = Path(__file__).resolve().parents[1] / "results/private-workbench-api"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _json_file(path, limit=MAX_JSON):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError(f"JSON input exceeds {limit} bytes")
    return json.loads(path.read_text())


def _requirements(path):
    value = _json_file(path, 65536)
    if not isinstance(value, dict):
        raise ValueError("Requirements must be a JSON object")
    if "requirements" in value:
        if set(value) - {"requirements", "brief"}:
            raise ValueError("Only requirements and brief fields are accepted")
        requirements, brief = value["requirements"], value.get("brief", {})
    else:
        requirements, brief = value, {}
    if (not isinstance(requirements, dict) or not 1 <= len(requirements) <= 50
            or any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", k)
                   or not isinstance(v, str) or not v.strip() or len(v) > 2000
                   for k, v in requirements.items()) or not isinstance(brief, dict)):
        raise ValueError("Supply 1..50 named textual requirements (IDs: letters, digits, _ or -; text: 1..2000 characters) and an object brief")
    _bytes(brief)  # Also rejects non-finite JSON values.
    return requirements, brief


def _file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def _source_identity(path):
    path = Path(path)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".png")
        members = [{"name": p.name, "sha256": _file_hash(p)} for p in files]
        return {"kind": "png_directory", "sha256": _sha(_bytes(members)), "members": members}
    return {"kind": "file", "name": path.name, "sha256": _file_hash(path)}


def _report(manifest, result=None):
    escape = lambda value: html.escape(str(value), quote=True)
    status = "Prepared — no model request sent" if result is None else {"pass": "No violation found in selected frames", "fail": "Reported violation in selected frames", "indeterminate": "Selected evidence is inconclusive"}[result["status"]]
    sections = ["<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>",
                "<title>BriefGuard review</title><style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;background:#f7f9fc;color:#142033}article{display:inline-block;margin:.5rem;padding:.7rem;background:white;border:1px solid #ccd5df;border-radius:8px}img{max-width:100%;image-rendering:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{padding:1rem;background:#fff0cb}li{margin:.5rem 0}</style>",
                f"<h1>BriefGuard video review</h1><h2>{escape(status)}</h2>",
                "<p class=notice>Only the selected frames are inspected. A pass cannot establish that the complete video complies. Preparation and response import are offline; explicit execution requires separate spending approval.</p>",
                f"<p>Method: {escape(manifest['method'])}; selected {len(manifest['frames'])} / {manifest['total_frames']} frames; duration {manifest['duration_seconds']:.3f}s. Requested model: {escape(manifest['model'])}.</p>",
                "<h2>Requirements</h2><ul>"]
    sections.extend(f"<li><strong>{escape(k)}</strong>: {escape(v)}</li>" for k, v in manifest["requirements"].items())
    sections.append("</ul><h2>Selected evidence</h2>")
    for frame in manifest["frames"]:
        sections.append(f"<article id='frame-{frame['index']}'><img src='{frame['file']}' alt='Selected frame {frame['index']}'><p>Frame {frame['index']} · {frame['timestamp_seconds']:.3f}s<br>Display duration {frame['duration_seconds']:.3f}s</p></article>")
    if result is not None:
        if result.get("mode") == "executed_vlm_workflow":
            sections.append("<h2>Execution findings</h2><p>Recorded by the explicitly authorized adapter with prepared-request matching. This selected-frame check is not a scored experiment or human ground truth.</p>")
            if result.get("error"):
                sections.append("<p class=notice>Operational error: " + escape(result["error"]) + ". No compliance judgment is available.</p>")
        else:
            sections.append("<h2>Imported findings</h2><p>Operator-supplied response; provider origin and association with this request are not authenticated. This is not a scored experiment or human ground truth.</p>")
        sections.append("<ul>")
        sections.extend(f"<li><a href='#frame-{item['frame_index']}'>Frame {item['frame_index']}</a> / {escape(item['requirement'])}: {escape(item['reason'])}</li>" for item in result["evidence"])
        sections.append("</ul><h3>Returned usage</h3><pre>" + escape(json.dumps(result.get("usage"), indent=2)) + "</pre>")
        if result.get("mode") == "executed_vlm_workflow":
            sections.append("<h3>Shared budget accounting</h3><p>These totals cover ALL workbench bundles sharing the ledger, not this clip alone. Known token-cost estimates are not a provider billing guarantee; attempts without usage are retained in reservations.</p><pre>" + escape(json.dumps(result.get("api_accounting"), indent=2)) + "</pre>")
    sections.append("<h2>Artifacts</h2><p><a href='manifest.json'>Preparation manifest</a> · <a href='request.json'>Prepared API request</a></p><p>Review privacy, model availability and a separately approved total spending limit before using an external execution tool. This directory can contain private footage and requirements.</p></html>")
    return "\n".join(sections)


def prepare(input_path, requirements_path, output_dir, method="uniform", budget=8,
            model=DEFAULT_MODEL, fps=None):
    """Create a new immutable preparation directory. Never sends an API request."""
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("Output already exists; preserve it and choose a new directory")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]+-\d{4}-\d{2}-\d{2}", model):
        raise ValueError("Use a dated model snapshot; availability is not checked offline")
    if type(budget) is not int or not 1 <= budget <= 32:
        raise ValueError("Frame budget must be an integer in 1..32")
    requirements, brief = _requirements(requirements_path)
    video = load_video(input_path, fps=fps)
    features = None if method == "uniform" else extract_features(video.frames, {"feature_mode": "global" if method == "change" else "all"})
    indices = select_frames(method, len(video.frames), budget, features)
    source_identity = _source_identity(input_path)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".briefguard-", dir=output_dir.parent))
    try:
        content = [{"type": "input_text", "text": json.dumps({"requirements": requirements, "brief": brief}, allow_nan=False)}]
        frames = []
        for index in indices:
            name = f"frame-{index:06d}.png"
            Image.fromarray(video.frames[index]).save(temporary / name)
            data = (temporary / name).read_bytes()
            frames.append({"index": index, "file": name, "sha256": _sha(data),
                           "timestamp_seconds": video.timestamps_seconds[index], "duration_seconds": video.durations_seconds[index]})
            content.extend([{"type": "input_text", "text": f"Original frame index: {index}"},
                            {"type": "input_image", "detail": "low", "image_url": "data:image/png;base64," + base64.b64encode(data).decode()}])
        payload = {"model": model, "store": False, "instructions": PROMPT,
                   "input": [{"role": "user", "content": content}], "max_output_tokens": 800,
                   "text": {"format": {"type": "json_schema", "name": "brief_review", "strict": True, "schema": SCHEMA}}}
        request = _bytes(payload)
        if len(request) > 16_000_000:
            raise ValueError("Prepared request exceeds 16 MB")
        (temporary / "request.json").write_bytes(request)
        manifest = {"schema_version": 1, "mode": "offline_preparation", "network_calls": 0,
                    "model": model, "method": method, "requested_budget": budget,
                    "total_frames": len(video.frames), "duration_seconds": sum(video.durations_seconds),
                    "normalized_size": [video.frames.shape[2], video.frames.shape[1]],
                    "requirements": requirements, "brief": brief, "source": source_identity,
                    "frames": frames, "request_sha256": _sha(request),
                    "preprocessed_frames": len(video.frames) if features else 0,
                    "limitation": "Selected-frame evidence only; no whole-video compliance or accuracy result"}
        encoded = _bytes(manifest)
        (temporary / "manifest.json").write_bytes(encoded)
        (temporary / "manifest.sha256").write_text(_sha(encoded) + "\n")
        (temporary / "report.html").write_text(_report(manifest))
        if output_dir.exists():
            raise ValueError("Output appeared during preparation; refusing to overwrite")
        temporary.rename(output_dir)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def validate_preparation(directory):
    """Detect accidental local artifact drift; hashes are not authentication."""
    directory = Path(directory)
    manifest = _json_file(directory / "manifest.json")
    if _file_hash(directory / "manifest.json") != (directory / "manifest.sha256").read_text().strip():
        raise ValueError("Preparation manifest changed")
    if _file_hash(directory / "request.json") != manifest["request_sha256"]:
        raise ValueError("Prepared request changed")
    for frame in manifest["frames"]:
        if type(frame["index"]) is not int or frame["file"] != f"frame-{frame['index']:06d}.png":
            raise ValueError("Invalid prepared frame path")
        if _file_hash(directory / frame["file"]) != frame["sha256"]:
            raise ValueError("Prepared frame changed")
    return manifest


def import_response(directory, response_path):
    """Validate a provider-shaped JSON file; no provider provenance is inferred."""
    directory = Path(directory)
    if (directory / "execution_result.json").exists():
        raise ValueError("This bundle already has an execution outcome; preserve it and prepare a separate bundle for imports")
    if (directory / "import.complete").exists():
        raise ValueError("An imported result already exists; preserve the original")
    manifest = validate_preparation(directory)
    # Parse, hash and preserve the same bounded byte snapshot, even if the
    # operator replaces the input file while this import is running.
    with Path(response_path).open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError(f"JSON input exceeds {MAX_JSON} bytes")
    response = json.loads(raw)
    if not isinstance(response, dict) or response.get("status") != "completed" or response.get("model") != manifest["model"]:
        raise ValueError("Response must be completed and match the exact prepared model")
    try:
        output = response["output"]
        if not isinstance(output, list):
            raise ValueError("Response output must be a list")
        messages = [item for item in output if item.get("type") == "message"]
        parts = [part for item in messages for part in item.get("content", [])]
        if any(part.get("type") == "refusal" for part in parts):
            raise ValueError("Refused response")
        text = "".join(part["text"] for part in parts if part.get("type") == "output_text")
        result = _validate_result(json.loads(text), [frame["index"] for frame in manifest["frames"]], manifest["requirements"])
        if any(not item["reason"].strip() or len(item["reason"]) > 4000 for item in result["evidence"]):
            raise ValueError("Evidence reason must contain 1..4000 characters and not be blank")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed response envelope") from exc
    result = {**result, "mode": "imported_not_authenticated", "model_version": response["model"],
              "response_id": response.get("id"), "usage": response.get("usage"),
              "prepared_request_sha256": manifest["request_sha256"], "raw_response_sha256": _sha(raw),
              "provenance": "Operator-supplied JSON; provider origin and request association are not authenticated", "network_calls_by_importer": 0}
    encoded = _bytes(result)
    report = _report(manifest, result)
    # Stage each file before publication; a completion marker is written LAST.
    # Interrupted imports can resume with exactly the same validated response.
    # Hashes detect accidental drift; local operator-owned files are not authenticated.
    if (directory / "imported_result.json").exists():
        prior = _json_file(directory / "imported_result.json")
        if prior != result:
            raise ValueError("Incomplete import belongs to a different response; preserve its artifacts")
    if (directory / "imported_response.json").exists() and (directory / "imported_response.json").read_bytes() != raw:
        raise ValueError("Incomplete import raw response differs; preserve its artifacts")
    temporary = Path(tempfile.mkdtemp(prefix=".import-", dir=directory))
    try:
        for name, data in (("imported_response.json", raw), ("imported_result.json", encoded),
                           ("report.html", report.encode()), ("import.complete", (result["raw_response_sha256"] + "\n").encode())):
            (temporary / name).write_bytes(data)
        for name in ("imported_response.json", "imported_result.json", "report.html", "import.complete"):
            (temporary / name).replace(directory / name)
    finally:
        shutil.rmtree(temporary)
    return result



def _accounting(directory):
    path = Path(directory) / "ledger.jsonl"
    entries = []
    if path.exists():
        with path.open() as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            entries = [json.loads(line) for line in stream if line.strip()]
    attempts = [item for item in entries if "reservation_usd" in item]
    known = [item["estimated_api_cost_usd"] for item in entries if item.get("estimated_api_cost_usd") is not None]
    return {"attempts": len(attempts), "reserved_usd": sum(item["reservation_usd"] for item in attempts),
            "known_usage_cost_estimate_usd": sum(known), "attempts_without_known_cost": len(attempts) - len(known),
            "scope": "shared workbench ledger across all bundles", "provider_billing_guarantee": False}


def execute(directory, approved=False, *, transport=None):
    """Execute only the fixed approved proposal, using ONE shared budget ledger.

    The flag records operator acknowledgement, not permission by itself. The
    CLI does not offer a ledger override: all workbench bundles share the cap.
    Tests patch API_DIRECTORY and inject fake transport; production uses HTTPS.
    Failed outcomes are retained and are not retried on subsequent invocations.
    """
    if approved is not True:
        raise ValueError("Separate OpenAI / gpt-4.1-mini-2025-04-14 / USD 0.50 approval is required")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing; no network request sent")
    directory = Path(directory)
    if (directory / "imported_result.json").exists() or (directory / "imported_response.json").exists():
        raise ValueError("This bundle contains an imported response; prepare a separate bundle for execution")
    manifest = validate_preparation(directory)
    if manifest["model"] != DEFAULT_MODEL:
        raise ValueError("Prepared model differs from the fixed approval contract")
    request = _json_file(directory / "request.json", 16_000_000)
    # Preserve inner text/key ordering from preparation. Manifest JSON sorts keys,
    # so reconstructing this text from the manifest would change request bytes.
    shared = json.loads(request["input"][0]["content"][0]["text"])
    if shared != {"requirements": manifest["requirements"], "brief": manifest["brief"]}:
        raise ValueError("Prepared request brief differs from manifest")
    canonical_payload = json.dumps(request, sort_keys=True).encode()
    request_id = _sha(canonical_payload)
    identity = {"manifest_sha256": _file_hash(directory / "manifest.json"),
                "prepared_request_file_sha256": manifest["request_sha256"],
                "adapter_payload_sha256": request_id, "shared_ledger": str(API_DIRECTORY.resolve())}
    target = directory / "execution_result.json"
    if target.exists():
        saved = _json_file(target)
        if saved.get("execution_identity") != identity:
            raise ValueError("Saved execution identity differs; preserve its artifacts")
        (directory / "report.html").write_text(_report(manifest, saved))
        return saved
    config = PilotConfig(model=DEFAULT_MODEL, max_requests=36, max_spend_usd=0.50,
                         reservation_usd=0.01, input_usd_per_million=0.4,
                         output_usd_per_million=1.6, authorized=True,
                         max_output_tokens=800, retries=1)
    transport_calls = 0
    def checked_transport(payload, key, timeout):
        nonlocal transport_calls
        if payload != canonical_payload:
            raise PilotError("Adapter payload differs from the prepared request; no network request sent")
        transport_calls += 1
        return (transport or _transport)(payload, key, timeout)
    adapter = ResponsesPilot(config, API_DIRECTORY, transport=checked_transport)
    frames = []
    for frame in manifest["frames"]:
        with Image.open(directory / frame["file"]) as image:
            frames.append(image.convert("RGB"))
    indices = [frame["index"] for frame in manifest["frames"]]
    cached = (API_DIRECTORY / (request_id + ".result.json")).exists()
    # Exclusive durable intent prevents a second process/restart from sending
    # again if an earlier attempt died before saving its outcome. It is not a
    # provider-side exactly-once guarantee: unresolved attempts need review.
    marker = directory / "execution.started.json"
    try:
        with marker.open("xb") as stream:
            stream.write(_bytes({"execution_identity": identity, "status": "outcome_pending"}))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise ValueError("Execution was already started without a saved outcome; automatic retry refused. Preserve this bundle and shared ledger for manual review") from None
    started = time.perf_counter()
    result = {"mode": "executed_vlm_workflow", "execution_identity": identity,
              "requested_model": DEFAULT_MODEL, "adapter_cache_present_before": cached,
              "provenance": "Authorized execution attempt; inspect status, request identity and raw receipts",
              "scope": "Selected-frame product check; not a human-scored research experiment"}
    try:
        response = adapter.verify(frames, indices, shared["requirements"], shared["brief"])
        if response.get("model_version") != DEFAULT_MODEL or response.get("request_id") != request_id:
            raise PilotError("Returned model or request identity differs; operational indeterminate")
        checked = _validate_result({"status": response.get("status"), "evidence": response.get("evidence")}, indices, shared["requirements"])
        if any(not item["reason"].strip() or len(item["reason"]) > 4000 for item in checked["evidence"]):
            raise PilotError("Invalid evidence explanation; operational indeterminate")
        result.update(response)
        result["mode"] = "executed_vlm_workflow"
        result["provenance"] = "Recorded adapter/cache response linked to the exact prepared payload"
    except (PilotError, ValueError, TypeError, KeyError) as exc:
        # Adapter retains raw response and usage before semantic validation.
        # Operational failures remain visible; a second invocation replays this
        # outcome rather than creating another billable recovery request.
        result.update(status="indeterminate", evidence=[], error=str(exc))
    result["transport_calls_recorded_execution"] = transport_calls
    result["verification_wall_seconds"] = time.perf_counter() - started
    result["api_accounting"] = _accounting(API_DIRECTORY)
    result["raw_response_location"] = str(API_DIRECTORY / (request_id + ".attempt-*.raw.json"))
    _atomic_result(target, result)
    (directory / "report.html").write_text(_report(manifest, result))
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Prepare selected frames and an unsent request, offline")
    prep.add_argument("--input", required=True)
    prep.add_argument("--requirements", required=True)
    prep.add_argument("--out", required=True)
    prep.add_argument("--method", choices=["uniform", "change", "adaptive"], default="uniform")
    prep.add_argument("--budget", type=int, default=8)
    prep.add_argument("--model", default=DEFAULT_MODEL)
    prep.add_argument("--fps", type=float)
    imp = sub.add_parser("import-response", help="Inspect an operator-supplied response; does not call a model")
    imp.add_argument("--directory", required=True)
    imp.add_argument("--response", required=True)
    run = sub.add_parser("execute", help="Send only after separate approval; all bundles share one spending ledger")
    run.add_argument("--directory", required=True)
    run.add_argument("--approve-openai-gpt41mini-usd050", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.input, args.requirements, args.out, args.method, args.budget, args.model, args.fps)
            print(json.dumps({"mode": result["mode"], "selected_frames": len(result["frames"]), "network_calls": 0, "report": str(Path(args.out) / "report.html")}))
        elif args.command == "import-response":
            print(json.dumps(import_response(args.directory, args.response), indent=2))
        else:
            print(json.dumps(execute(args.directory, args.approve_openai_gpt41mini_usd050), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Review workflow refused: {exc}\n")


if __name__ == "__main__":
    main()

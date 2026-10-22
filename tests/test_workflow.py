"""Offline workflow integration tests; response fixtures are not model evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from briefguard.workflow import DEFAULT_MODEL, execute, import_response, prepare, validate_preparation


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "input.npz"
        frames = np.zeros((12, 16, 24, 3), dtype=np.uint8)
        frames[5:7, :, :, 0] = 255
        np.savez(self.video, frames=frames, fps=6)
        self.requirements = self.root / "requirements.json"
        self.requirements.write_text(json.dumps({"requirements": {"visible": "Object <script>alert(1)</script> remains visible"}, "brief": {"product": "sample"}}))
        self.output = self.root / "prepared"

    def prepare(self, **kwargs):
        return prepare(self.video, self.requirements, self.output, budget=4, **kwargs)

    def response(self, result, **changes):
        raw = {"status": "completed", "model": DEFAULT_MODEL, "id": "TEST_FIXTURE_NOT_A_REAL_CALL",
               "usage": {"input_tokens": 100, "output_tokens": 20},
               "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}
        raw.update(changes)
        path = self.root / "response.json"
        path.write_text(json.dumps(raw))
        return path

    def test_prepare_all_samplers_without_network_and_immutable_output(self):
        for method in ("uniform", "change", "adaptive"):
            with self.subTest(method=method), patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network forbidden")):
                self.output = self.root / method
                manifest = self.prepare(method=method)
                self.assertEqual(4, len(manifest["frames"]))
                self.assertEqual(2, manifest["duration_seconds"])
                self.assertEqual(manifest, validate_preparation(self.output))
                request = json.loads((self.output / "request.json").read_text())
                images = [x for x in request["input"][0]["content"] if x["type"] == "input_image"]
                self.assertEqual(4, len(images))
                self.assertTrue(all(x["image_url"].startswith("data:image/png;base64,") for x in images))
                self.assertFalse(request["store"])
                self.assertEqual(0, manifest["network_calls"])
                report = (self.output / "report.html").read_text()
                self.assertIn("Prepared — no model request sent", report)
                self.assertNotIn("<script>", report)
                with self.assertRaisesRegex(ValueError, "already exists"):
                    self.prepare(method=method)

    def test_import_is_explicitly_unauthenticated_and_escaped(self):
        manifest = self.prepare()
        result = {"status": "fail", "evidence": [{"frame_index": manifest["frames"][0]["index"], "requirement": "visible", "reason": "<script>bad()</script>"}]}
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network forbidden")):
            imported = import_response(self.output, self.response(result))
        self.assertEqual("imported_not_authenticated", imported["mode"])
        self.assertEqual(0, imported["network_calls_by_importer"])
        report = (self.output / "report.html").read_text()
        self.assertIn("not authenticated", report)
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;bad()", report)
        with self.assertRaisesRegex(ValueError, "already exists"):
            import_response(self.output, self.root / "response.json")

    def test_unsupplied_frame_unknown_requirement_and_contradiction_rejected(self):
        manifest = self.prepare()
        index = manifest["frames"][0]["index"]
        bad_results = [
            {"status": "fail", "evidence": [{"frame_index": 999, "requirement": "visible", "reason": "wrong"}]},
            {"status": "fail", "evidence": [{"frame_index": index, "requirement": "unknown", "reason": "wrong"}]},
            {"status": "fail", "evidence": []},
            {"status": "pass", "evidence": [{"frame_index": index, "requirement": "visible", "reason": "wrong"}]},
        ]
        for result in bad_results:
            with self.subTest(result=result), self.assertRaises(ValueError):
                import_response(self.output, self.response(result))
            self.assertFalse((self.output / "imported_result.json").exists())

    def test_blank_and_excessive_evidence_reason_rejected(self):
        manifest = self.prepare()
        for reason in ("", " \n\t", "x" * 4001):
            with self.subTest(reason_length=len(reason)), self.assertRaisesRegex(ValueError, "Evidence reason"):
                import_response(self.output, self.response({"status": "fail", "evidence": [{
                    "frame_index": manifest["frames"][0]["index"], "requirement": "visible", "reason": reason}]}))
        self.assertFalse((self.output / "import.complete").exists())

    def test_import_preserves_the_same_bytes_it_validated(self):
        self.prepare()
        path = self.response({"status": "pass", "evidence": []})
        original = path.read_bytes()
        from briefguard import workflow
        validate = workflow._validate_result
        def replace_input(*args):
            path.write_text('{"unrelated": true}')
            return validate(*args)
        with patch.object(workflow, "_validate_result", side_effect=replace_input):
            result = import_response(self.output, path)
        self.assertEqual(original, (self.output / "imported_response.json").read_bytes())
        self.assertEqual(workflow._sha(original), result["raw_response_sha256"])

    def test_wrong_model_incomplete_refused_and_malformed_rejected(self):
        self.prepare()
        for changes in ({"model": "different-model-2025-04-14"}, {"status": "incomplete"},
                        {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]},
                        {"output": [None]}, {"output": "bad"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                import_response(self.output, self.response({"status": "pass", "evidence": []}, **changes))
        self.assertFalse((self.output / "imported_result.json").exists())

    def test_changed_frame_or_request_rejected(self):
        manifest = self.prepare()
        frame = self.output / manifest["frames"][0]["file"]
        original = frame.read_bytes()
        frame.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "frame changed"):
            validate_preparation(self.output)
        frame.write_bytes(original)
        (self.output / "request.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "request changed"):
            import_response(self.output, self.response({"status": "pass", "evidence": []}))

    def test_invalid_requirements_and_limits_leave_no_output(self):
        for value in ({}, {"bad id": "text"}, {"rule": ""}, {"requirements": {"rule": "x"}, "brief": []}):
            self.requirements.write_text(json.dumps(value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.output.exists())
        self.requirements.write_text(json.dumps({"rule": "visible"}))
        for budget in (0, 33, True):
            with self.assertRaises(ValueError):
                prepare(self.video, self.requirements, self.output, budget=budget)
        with self.assertRaisesRegex(ValueError, "dated model"):
            self.prepare(model="model-alias")
        self.assertFalse(self.output.exists())

    def test_interrupted_import_resumes_same_response_only(self):
        self.prepare()
        path = self.response({"status": "pass", "evidence": []})
        original_replace = Path.replace
        def fail_report(source, target):
            if source.name == "report.html":
                raise OSError("simulated interruption")
            return original_replace(source, target)
        with patch.object(Path, "replace", fail_report), self.assertRaises(OSError):
            import_response(self.output, path)
        self.assertFalse((self.output / "import.complete").exists())
        self.assertTrue((self.output / "imported_result.json").exists())
        raw = path.read_bytes()
        self.response({"status": "indeterminate", "evidence": []})
        with self.assertRaisesRegex(ValueError, "different response"):
            import_response(self.output, path)
        path.write_bytes(raw)
        import_response(self.output, path)
        self.assertTrue((self.output / "import.complete").exists())
        self.assertIn("No violation found in selected frames", (self.output / "report.html").read_text())

    def test_execute_requires_approval_key_and_exact_model(self):
        from briefguard import workflow
        self.prepare(model="other-model-2025-04-14")
        with patch.dict("os.environ", {}, clear=True), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            with self.assertRaisesRegex(ValueError, "approval"):
                execute(self.output)
            with self.assertRaisesRegex(ValueError, "missing"):
                execute(self.output, approved=True)
            with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}):
                with self.assertRaisesRegex(ValueError, "model differs"):
                    execute(self.output, approved=True)
        self.assertFalse((self.root / "ledger").exists())

    def test_execute_exact_request_shared_cache_and_identity(self):
        from briefguard import workflow
        # Deliberately non-alphabetical IDs exercise ordered inner input_text.
        self.requirements.write_text(json.dumps({"requirements": {"z_last": "visible", "a_first": "blue"}, "brief": {"z": 2, "a": 1}}))
        self.prepare()
        raw = self.response({"status": "pass", "evidence": []}).read_bytes()
        sent = []
        def fake(payload, key, timeout):
            sent.append(payload)
            self.assertEqual(json.loads((self.output / "request.json").read_text()), json.loads(payload))
            return 200, raw, {}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            first = execute(self.output, approved=True, transport=fake)
            self.assertEqual("pass", first["status"])
            self.assertEqual("executed_vlm_workflow", first["mode"])
            self.assertEqual(1, first["api_accounting"]["attempts"])
            self.assertEqual(first, execute(self.output, approved=True, transport=fake))
            self.output = self.root / "second_bundle"
            self.prepare()
            second = execute(self.output, approved=True, transport=fake)
            self.assertTrue(second["adapter_cache_present_before"])
            self.assertEqual(1, len(sent))
            self.assertEqual(1, second["api_accounting"]["attempts"])
            data = json.loads((self.output / "execution_result.json").read_text())
            data["execution_identity"]["adapter_payload_sha256"] = "changed"
            (self.output / "execution_result.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "identity differs"):
                execute(self.output, approved=True, transport=fake)

    def test_execute_wrong_model_or_timeout_retained_as_indeterminate(self):
        from briefguard import workflow
        for scenario in ("model", "timeout"):
            self.output = self.root / scenario
            self.prepare()
            calls = []
            raw = self.response({"status": "pass", "evidence": []}, model="wrong-model").read_bytes()
            def fake(payload, key, timeout):
                calls.append(payload)
                if scenario == "timeout":
                    raise TimeoutError("fixture")
                return 200, raw, {}
            with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / (scenario + "_ledger")):
                result = execute(self.output, approved=True, transport=fake)
                self.assertEqual("indeterminate", result["status"])
                self.assertIn("error", result)
                self.assertEqual(1, result["api_accounting"]["attempts"])
                self.assertEqual(result, execute(self.output, approved=True, transport=fake))
                self.assertEqual(1, len(calls))

    def test_execute_interruption_before_outcome_refuses_automatic_restart(self):
        from briefguard import workflow
        self.prepare()
        calls = []
        def timeout_after_send(*args):
            calls.append(True)
            raise TimeoutError("unknown provider outcome")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            with patch.object(workflow, "_atomic_result", side_effect=OSError("simulated process interruption")), self.assertRaises(OSError):
                execute(self.output, approved=True, transport=timeout_after_send)
            self.assertTrue((self.output / "execution.started.json").exists())
            self.assertFalse((self.output / "execution_result.json").exists())
            with self.assertRaisesRegex(ValueError, "automatic retry refused"):
                execute(self.output, approved=True, transport=timeout_after_send)
            self.assertEqual(1, len(calls))
            self.assertEqual(1, workflow._accounting(self.root / "ledger")["attempts"])

    def test_execute_shared_budget_exhaustion_does_not_send(self):
        from briefguard import workflow
        self.prepare()
        raw = self.response({"status": "pass", "evidence": []}).read_bytes()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            execute(self.output, approved=True, transport=lambda *args: (200, raw, {}))
            with (self.root / "ledger/ledger.jsonl").open("a") as stream:
                for attempt in range(2, 37):
                    stream.write(json.dumps({"attempt": attempt, "reservation_usd": 0.01, "request_id": "FIXTURE"}) + "\n")
            self.output = self.root / "another"
            self.requirements.write_text(json.dumps({"different": "New request"}))
            self.prepare()
            result = execute(self.output, approved=True, transport=lambda *args: self.fail("Budget exhaustion must not send"))
            self.assertEqual("indeterminate", result["status"])
            self.assertIn("budget exhausted", result["error"])
            self.assertEqual(36, result["api_accounting"]["attempts"])

    def test_execute_and_import_outcomes_cannot_silently_replace_each_other(self):
        from briefguard import workflow
        self.prepare()
        path = self.response({"status": "pass", "evidence": []})
        raw = path.read_bytes()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            execute(self.output, approved=True, transport=lambda *args: (200, raw, {}))
            with self.assertRaisesRegex(ValueError, "execution outcome"):
                import_response(self.output, path)
            self.output = self.root / "imported"
            self.prepare()
            import_response(self.output, path)
            with self.assertRaisesRegex(ValueError, "imported response"):
                execute(self.output, approved=True, transport=lambda *args: self.fail("No send"))

    def test_execute_payload_drift_stops_before_transport(self):
        from briefguard import workflow
        self.prepare()
        path = self.output / "request.json"
        payload = json.loads(path.read_text())
        payload["instructions"] = "Changed instructions"
        path.write_text(json.dumps(payload))
        manifest = json.loads((self.output / "manifest.json").read_text())
        manifest["request_sha256"] = workflow._file_hash(path)
        encoded = workflow._bytes(manifest)
        (self.output / "manifest.json").write_bytes(encoded)
        (self.output / "manifest.sha256").write_text(workflow._sha(encoded))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "UNIT_TEST_FAKE_KEY"}), patch.object(workflow, "API_DIRECTORY", self.root / "ledger"):
            result = execute(self.output, approved=True, transport=lambda *args: self.fail("Mismatch must not send"))
            self.assertEqual("indeterminate", result["status"])
            self.assertIn("payload differs", result["error"])

    def test_oversized_response_rejected(self):
        self.prepare()
        path = self.root / "large.json"
        path.write_bytes(b" " * 4_000_001)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            import_response(self.output, path)
        self.assertFalse((self.output / "imported_result.json").exists())


if __name__ == "__main__":
    unittest.main()

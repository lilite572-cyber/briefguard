"""Guarded pilot tests use only temporary fixtures, fake keys and fake HTTP."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from briefguard import pilot_v2
from scripts import run_pilot_guarded as guarded


class GuardedPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "FIXTURE_NOT_NASA.gif"
        frames = [Image.fromarray(np.full((24, 24, 3), i * 15, dtype=np.uint8)) for i in range(12)]
        frames[0].save(self.source, save_all=True, append_images=frames[1:], duration=500, loop=0)
        config = json.loads(pilot_v2.CONFIG.read_text())
        config["natural_source"]["expected_sha256"] = pilot_v2.digest(self.source.read_bytes())
        self.config = self.root / "fixture-config.json"
        self.config.write_text(json.dumps(config))
        self.config_patch = patch.object(pilot_v2, "CONFIG", self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.env_patch = patch.dict(os.environ, {"OPENAI_API_KEY": "UNIT_TEST_NOT_A_REAL_KEY"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.block_network = patch.object(guarded, "_transport", side_effect=AssertionError("Real transport forbidden in test"))
        self.block_network.start()
        self.addCleanup(self.block_network.stop)
        self.directory = self.root / "packet"
        self.plan = pilot_v2.prepare(self.directory, self.source)

    def review_fixture(self):
        # These are explicitly synthetic UNIT_TEST labels, never real human work.
        path = self.directory / "human_review.csv"
        with path.open() as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        for row in rows:
            row.update(label="pass", reviewer="UNIT_TEST_NOT_A_HUMAN")
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        path = self.directory / "source_confirmation.json"
        source = json.loads(path.read_text())
        source.update(reviewer="UNIT_TEST_NOT_A_HUMAN", confirmed_exact_nasa_source=True)
        path.write_text(json.dumps(source))

    def fake_response(self, usage=True):
        response = {"id": "UNIT_TEST_RESPONSE", "model": "gpt-4.1-mini-2025-04-14", "status": "completed",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"status": "pass", "evidence": []})}]}]}
        if usage:
            response["usage"] = {"input_tokens": 100, "output_tokens": 10}
        return 200, json.dumps(response).encode(), {}

    def test_blank_review_and_source_confirmation_block_without_writes_or_http(self):
        before = {p.relative_to(self.directory) for p in self.directory.rglob("*")}
        check = guarded.readiness(self.directory)
        self.assertFalse(check["ready"])
        self.assertTrue(any("Human review" in reason for reason in check["reasons"]))
        result = guarded.execute(self.directory, approved=True, transport=lambda *args: self.fail("No HTTP"))
        self.assertEqual("blocked", result["status"])
        self.assertEqual(before, {p.relative_to(self.directory) for p in self.directory.rglob("*")})
        self.assertFalse((self.directory / "guarded_execution_identity.json").exists())

    def test_check_only_does_not_need_key_but_execution_does(self):
        self.review_fixture()
        before = {p.relative_to(self.directory) for p in self.directory.rglob("*")}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guarded.main(["--directory", str(self.directory), "--check-only"])
        self.assertEqual(0, code)
        self.assertEqual("ready", json.loads(out.getvalue())["status"])
        self.assertEqual(before, {p.relative_to(self.directory) for p in self.directory.rglob("*")})
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, guarded.main(["--directory", str(self.directory), "--check-only"]))
            result = guarded.execute(self.directory, approved=True, transport=lambda *args: self.fail("No HTTP without key"))
            self.assertEqual("blocked", result["status"])
            self.assertTrue(any("OPENAI_API_KEY" in reason for reason in result["reasons"]))
        self.assertFalse((self.directory / "guarded_execution_identity.json").exists())

    def test_successful_fake_execution_binds_runner_and_resumes_without_http(self):
        self.review_fixture()
        calls = []
        def fake(*args):
            calls.append(True)
            return self.fake_response()
        result = guarded.execute(self.directory, approved=True, transport=fake)
        self.assertEqual("completed", result["status"])
        self.assertGreater(len(calls), 0)
        self.assertLessEqual(len(calls), 18)
        identity = json.loads((self.directory / "guarded_execution_identity.json").read_text())
        self.assertEqual(guarded._sha(guarded.RUNNER_PATH), identity["runner_sha256"])
        before = len(calls)
        again = guarded.execute(self.directory, approved=True, transport=fake)
        self.assertEqual("completed", again["status"])
        self.assertEqual(0, again["network_calls"])
        self.assertEqual(before, len(calls))
        identity["runner_sha256"] = "changed"
        (self.directory / "guarded_execution_identity.json").write_text(json.dumps(identity))
        self.assertFalse(guarded.readiness(self.directory)["ready"])

    def test_missing_usage_halts_before_second_http_and_keeps_reservations(self):
        self.review_fixture()
        calls = []
        def fake(*args):
            calls.append(True)
            return self.fake_response(usage=False)
        result = guarded.execute(self.directory, approved=True, transport=fake)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(1, len(calls))
        self.assertTrue(any("unknown or invalid usage" in reason for reason in result["reasons"]))
        entries = guarded._ledger(self.directory)
        self.assertEqual(2, sum("reservation_usd" in entry for entry in entries))
        self.assertTrue((self.directory / "guarded_execution_events.jsonl").exists())
        self.assertEqual("blocked", guarded.execute(self.directory, approved=True, transport=fake)["status"])
        self.assertEqual(1, len(calls))

    def test_transport_unknown_halts_before_second_http(self):
        self.review_fixture()
        calls = []
        def fake(*args):
            calls.append(True)
            raise TimeoutError("UNIT_TEST_UNKNOWN_OUTCOME")
        result = guarded.execute(self.directory, approved=True, transport=fake)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(1, len(calls))
        self.assertTrue(any("transport/outcome unresolved" in reason for reason in result["reasons"]))

    def test_prior_pending_reservation_blocks_before_any_http(self):
        self.review_fixture()
        api = self.directory / "api"
        api.mkdir()
        (api / "ledger.jsonl").write_text(json.dumps({"request_id": "previous", "attempt": 1, "reservation_usd": 0.01}) + "\n")
        result = guarded.execute(self.directory, approved=True, transport=lambda *args: self.fail("No HTTP"))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("pending" in reason for reason in result["reasons"]))
        self.assertFalse((self.directory / "guarded_execution_identity.json").exists())

    def test_reserved_retry_statuses_remain_allowed(self):
        for status in (429, 500, 503, 599):
            entries = [{"attempt": 1, "reservation_usd": 0.01}, {"attempt": 1, "http_status": status},
                       {"attempt": 2, "reservation_usd": 0.01}]
            self.assertEqual([], guarded.ledger_problems(entries, exclude_attempt=2))
        self.assertTrue(guarded.ledger_problems([{ "attempt": 1, "reservation_usd": 0.01}, {"attempt": 1, "http_status": 200}, {"attempt": 1, "estimated_api_cost_usd": None}]))


if __name__ == "__main__":
    unittest.main()

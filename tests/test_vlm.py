import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from briefguard.vlm import PilotConfig, PilotError, ResponsesPilot


def config(**overrides):
    values = dict(model="test-model-2026-10-01", max_requests=3, max_spend_usd=.3,
                  reservation_usd=.1, input_usd_per_million=1, output_usd_per_million=2,
                  authorized=True)
    return PilotConfig(**{**values, **overrides})


def response(result=None, **overrides):
    result = result or {"status": "pass", "evidence": []}
    value = {"id": "response-test", "status": "completed", "model": "test-model-2026-10-01",
             "usage": {"input_tokens": 100, "output_tokens": 20},
             "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}
    return 200, json.dumps({**value, **overrides}).encode(), {}


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.environment = patch.dict("os.environ", {"OPENAI_API_KEY": "FAKE_TEST_KEY"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.frames = [Image.new("RGB", (16, 16), "blue")]
        self.requirements = {"color": "Package remains blue"}

    def run_pilot(self, transport, cfg=None, indices=None):
        pilot = ResponsesPilot(cfg or config(), self.tmp.name, transport=transport, sleep=lambda _: None)
        return pilot.verify(self.frames, indices or [9], self.requirements, {"product": "example"})

    def test_no_config_authorization_or_snapshot_fails_closed(self):
        with self.assertRaises(ValueError):
            ResponsesPilot()
        for cfg in (config(authorized=False), config(model="latest"), config(reservation_usd=0),
                    config(max_spend_usd=float("nan")), config(retries=3)):
            with self.assertRaises(ValueError):
                ResponsesPilot(cfg, self.tmp.name)

    def test_success_encodes_images_and_caches_without_network(self):
        calls = []
        def transport(payload, key, timeout):
            calls.append(json.loads(payload))
            self.assertEqual(key, "FAKE_TEST_KEY")
            return response()
        result = self.run_pilot(transport)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["usage"]["input_tokens"], 100)
        self.assertFalse(calls[0]["store"])
        self.assertEqual(calls[0]["input"][0]["content"][2]["image_url"][:22], "data:image/png;base64,")
        self.assertTrue(calls[0]["text"]["format"]["strict"])
        self.run_pilot(lambda *args: self.fail("cache made a request"))
        self.assertEqual(len(calls), 1)
        all_logs = b"".join(path.read_bytes() for path in Path(self.tmp.name).glob("*"))
        self.assertNotIn(b"FAKE_TEST_KEY", all_logs)

    def test_each_http_retry_reserves_and_persists_budget(self):
        calls = []
        def transport(*args):
            calls.append(1)
            return (503, b'{"error":"temporary"}', {}) if len(calls) == 1 else response()
        result = self.run_pilot(transport, config(max_requests=2))
        self.assertAlmostEqual(result["reservation_spent_usd"], .2)
        with self.assertRaises(PilotError):
            self.run_pilot(lambda *args: self.fail("budget exceeded"), config(max_requests=2), [10])
        self.assertEqual(len(calls), 2)

    def test_reservation_dollar_limit_stops_retry(self):
        calls = []
        def transport(*args):
            calls.append(1)
            return 429, b'{}', {}
        with self.assertRaises(PilotError):
            self.run_pilot(transport, config(max_spend_usd=.1))
        self.assertEqual(len(calls), 1)

    def test_timeout_is_not_retried_or_refunded(self):
        calls = []
        def transport(*args):
            calls.append(1)
            raise TimeoutError("fake")
        with self.assertRaises(PilotError):
            self.run_pilot(transport, config(max_requests=1))
        with self.assertRaises(PilotError):
            self.run_pilot(lambda *args: self.fail("timeout refunded"), config(max_requests=1))
        self.assertEqual(len(calls), 1)

    def test_invalid_frame_and_requirement_citations_are_rejected(self):
        invalid = [
            {"frame_index": 999, "requirement": "color", "reason": "wrong"},
            {"frame_index": 9, "requirement": "unknown", "reason": "wrong"},
            {"frame_index": True, "requirement": "color", "reason": "wrong"},
        ]
        for evidence in invalid:
            with tempfile.TemporaryDirectory() as directory:
                pilot = ResponsesPilot(config(), directory, transport=lambda *a: response({"status": "fail", "evidence": [evidence]}))
                with self.assertRaises(PilotError):
                    pilot.verify(self.frames, [9], self.requirements, {})

    def test_incomplete_refusal_is_not_a_pass(self):
        with self.assertRaises(PilotError):
            self.run_pilot(lambda *a: response(status="incomplete"))

    def test_malformed_response_structure_is_an_operational_error(self):
        for reply in ((200, b'[]', {}), response(output=[None])):
            with self.subTest(reply=reply), self.assertRaises(PilotError):
                self.run_pilot(lambda *a: reply)
        self.assertEqual(list(Path(self.tmp.name).glob("*.result.json")), [])

    def test_errors_redact_key_and_do_not_retry_auth_failure(self):
        calls = []
        def transport(*args):
            calls.append(1)
            return 401, b'{"error":"FAKE_TEST_KEY invalid"}', {}
        with self.assertRaises(PilotError):
            self.run_pilot(transport)
        self.assertEqual(len(calls), 1)
        raw = next(Path(self.tmp.name).glob("*.raw.json")).read_text()
        self.assertNotIn("FAKE_TEST_KEY", raw)
        self.assertIn("REDACTED_API_KEY", raw)

    def test_configuration_cannot_reset_existing_ledger(self):
        self.run_pilot(lambda *a: response())
        with self.assertRaises(PilotError):
            self.run_pilot(lambda *a: self.fail("configuration reset"), config(max_requests=99))

    def test_missing_key_fails_before_transport(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with self.assertRaises(PilotError):
                self.run_pilot(lambda *a: self.fail("sent without key"))

    def test_usage_cost_uses_reviewed_rates_and_keeps_reservation_separate(self):
        result = self.run_pilot(lambda *a: response())
        self.assertAlmostEqual(result["estimated_api_cost_usd"], .00014)
        self.assertAlmostEqual(result["reservation_spent_usd"], .1)
        self.assertFalse(result["budget_halted"])
        entries = [json.loads(line) for line in (Path(self.tmp.name) / "ledger.jsonl").read_text().splitlines()]
        self.assertAlmostEqual(entries[-1]["estimated_api_cost_usd"], .00014)

    def test_usage_above_reservation_halts_future_requests_but_allows_replay(self):
        result = self.run_pilot(lambda *a: response(usage={"input_tokens": 400_000, "output_tokens": 20}))
        self.assertAlmostEqual(result["estimated_api_cost_usd"], .40004)
        self.assertTrue(result["budget_halted"])
        self.run_pilot(lambda *a: self.fail("cached replay made a request"))
        with self.assertRaisesRegex(PilotError, "further requests halted"):
            self.run_pilot(lambda *a: self.fail("overrun made a request"), indices=[10])

    def test_incomplete_response_overrun_is_still_accounted(self):
        with self.assertRaises(PilotError):
            self.run_pilot(lambda *a: response(status="incomplete", usage={"input_tokens": 400_000, "output_tokens": 20}))
        with self.assertRaisesRegex(PilotError, "further requests halted"):
            self.run_pilot(lambda *a: self.fail("incomplete overrun ignored"))

    def test_failed_atomic_cache_replacement_leaves_no_partial_result(self):
        with patch("briefguard.vlm.os.replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.run_pilot(lambda *a: response())
        self.assertEqual(list(Path(self.tmp.name).glob("*.result.json")), [])
        self.assertEqual(list(Path(self.tmp.name).glob("*.tmp")), [])
        self.assertTrue(list(Path(self.tmp.name).glob("*.raw.json")))


if __name__ == "__main__":
    unittest.main()

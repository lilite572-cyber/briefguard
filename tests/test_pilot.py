"""Offline integration checks. Test labels/footage are fixtures, never human evidence."""
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from briefguard.pilot import prepare, run, validate_preparation, summarize


class PilotWorkflowTests(unittest.TestCase):
    def test_no_approval_refuses_before_reading(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            run("does-not-exist")

    def test_partial_plan_drift_and_missing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            plan = prepare(path)
            self.assertEqual(len(plan["jobs"]), 9)
            self.assertFalse(plan["complete_data"])
            self.assertEqual(plan["live_requests"], 0)
            with self.assertRaisesRegex(ValueError, "Natural source"):
                run(path, approved=True)
            with self.assertRaisesRegex(ValueError, "immutable"):
                prepare(path)
            (path / "plan.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "plan drift"):
                validate_preparation(path)

    def test_budget_edit_is_rejected_even_if_sidecar_is_rewritten(self):
        from briefguard.pilot import digest
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            plan = prepare(path)
            plan["config"]["max_spend_usd"] = 100
            (path / "plan.json").write_text(json.dumps(plan))
            (path / "plan.sha256").write_text(digest((path / "plan.json").read_bytes()))
            with self.assertRaisesRegex(ValueError, "budget/model"):
                validate_preparation(path)

    def test_pixel_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            prepare(path)
            (path / "case-01.npy").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "pixel file drift"):
                validate_preparation(path)

    def test_full_fake_transport_resume_and_label_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            source = path / "fixture.gif"
            # This is a unit-test fixture, not the claimed NASA research source.
            frames = [Image.fromarray(np.full((32, 32, 3), i * 10, dtype=np.uint8)) for i in range(20)]
            frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)
            out = path / "out"
            plan = prepare(out, source)
            self.assertEqual(len(plan["jobs"]), 18)
            calls = []
            def transport(payload, key, timeout):
                calls.append(payload)
                result = {"status": "pass", "evidence": []}
                response = {"status": "completed", "model": "gpt-4.1-mini-2025-04-14", "id": "fake",
                            "usage": {"input_tokens": 100, "output_tokens": 10},
                            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}
                return 200, json.dumps(response).encode(), {}
            with self.assertRaisesRegex(ValueError, "Human labels"):
                run(out, approved=True, transport=transport)
            with (out / "human_review.csv").open(newline="") as stream:
                reader = csv.DictReader(stream)
                fields, rows = reader.fieldnames, list(reader)
            for row in rows:
                row.update(label="pass", reviewer="UNIT_TEST_NOT_HUMAN")
            with (out / "human_review.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader(); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "confirmation"):
                run(out, approved=True, transport=transport)
            review = json.loads((out / "source_confirmation.json").read_text())
            review.update(reviewer="UNIT_TEST_NOT_HUMAN", confirmed_exact_nasa_source=True)
            (out / "source_confirmation.json").write_text(json.dumps(review))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-never-sent"}):
                summary = run(out, approved=True, transport=transport)
                before = len(calls)
                self.assertGreater(before, 0)
                self.assertLessEqual(before, 18)
                self.assertEqual(run(out, approved=True, transport=transport), summary)
                self.assertEqual(len(calls), before)
                with (out / "human_review.csv").open("a") as stream:
                    stream.write("\n")
                with self.assertRaisesRegex(ValueError, "labels changed"):
                    run(out, approved=True, transport=transport)

    def test_unknowns_and_operational_errors_are_not_approvals(self):
        plan = {"cases": [{"case_id": "a", "origin": "synthetic"}, {"case_id": "b", "origin": "synthetic"}]}
        outcomes = [{"case_id": "a", "method": "uniform", "selected_indices": [2], "result": {"status": "indeterminate"}, "error": "timeout"},
                    {"case_id": "b", "method": "uniform", "selected_indices": [2], "result": {"status": "pass"}}]
        labels = {"a": {"label": "fail", "start_frame": 2, "end_frame": 3}, "b": {"label": "indeterminate"}}
        row = summarize(plan, outcomes, labels)["groups"]["synthetic/uniform"]
        self.assertEqual(row["positive"], 1)
        self.assertEqual(row["unknown"], 1)
        self.assertEqual(row["false_approved"], 0)
        self.assertEqual(row["captured_but_missed"], 1)
        self.assertEqual(row["operational_errors"], 1)


if __name__ == "__main__":
    unittest.main()

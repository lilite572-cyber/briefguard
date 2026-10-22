"""Tests for faithful, safe replay export without production-model calls."""

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from briefguard.demo_export import _summarize, choose_cases, export_demo


def row(clip_id, method, violated, predicted, hit=False, source_id=1):
    return {"clip_id": clip_id, "source_id": source_id, "split": "test", "budget": 8,
            "method": method, "annotation": {"violated": violated,
            "violation_type": "wrong_color" if violated else None,
            "start_frame": 1 if violated else None, "end_frame": 2 if violated else None,
            "duration_frames": 1 if violated else 0, "motion": "quiet"},
            "selected_indices": [0, 1], "prediction": {"violated": predicted, "evidence": []},
            "sampling_hit": hit, "timing": {"prepass_s": .001, "verification_s": .002}}


class DemoTests(unittest.TestCase):
    def test_case_selection_includes_clean_and_adaptive_failure(self):
        rows = [row("a", "adaptive", False, False), row("b", "adaptive", True, False),
                row("c", "adaptive", True, True)]
        picked = choose_cases(rows)
        self.assertEqual(picked[0], ("a", "Compliant control"))
        self.assertEqual(picked[1], ("b", "Adaptive false approval"))
        self.assertEqual(len({key for key, _ in picked}), len(picked))

    def test_summary_uses_all_rows_and_separates_unknowns(self):
        rows = [row("a", "uniform", True, True), row("b", "uniform", True, False),
                row("c", "uniform", True, None), row("d", "uniform", False, False)]
        result = _summarize(rows)[0]
        self.assertEqual(result["positive_count"], 3)
        self.assertEqual(result["recall"], 1 / 3)
        self.assertEqual(result["false_approval_rate"], 1 / 3)
        self.assertEqual(result["false_positive_rate"], 0)
        self.assertAlmostEqual(result["mean_pipeline_ms"], 3)

    def test_export_regenerates_and_uses_safe_asset_filenames(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            results = base / "run"
            results.mkdir()
            record = row("../../untrusted", "uniform", False, False)
            (results / "predictions.jsonl").write_text(json.dumps(record) + "\n")
            frames = np.zeros((4, 4, 6, 3), dtype=np.uint8)
            clip = SimpleNamespace(clip_id=record["clip_id"], source_id=1, frames=frames,
                                   brief={"requirements": ["A visible product"]}, annotation=record["annotation"])
            with patch("briefguard.data.iter_clips", return_value=iter([clip])):
                output = export_demo(results, base / "viewer", {"fps": 24})
            self.assertEqual(output["clips"], 1)
            payload = json.loads((base / "viewer" / "data.json").read_text())
            self.assertEqual(payload["mode"], "replay")
            self.assertEqual(payload["human_audit"], "pending")
            asset = payload["clips"][0]["sprite_url"]
            self.assertNotIn("..", asset)
            self.assertTrue((base / "viewer" / asset).is_file())
            self.assertEqual(payload["clips"][0]["methods"]["uniform"], record)
            script = (base / "viewer" / "data.js").read_text()
            self.assertTrue(script.startswith("window.BRIEFGUARD_DATA = "))
            self.assertEqual(json.loads(script.split(" = ", 1)[1].rstrip(";\n")), payload)
            with (base / "viewer" / "human_review.csv").open() as handle:
                audit = list(csv.DictReader(handle))
            self.assertEqual(audit[0]["human_decision"], "")
            self.assertEqual(audit[0]["reviewer"], "")

    def test_export_rejects_reconstruction_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            record = row("clip", "uniform", False, False)
            record["pixels_sha256"] = "not-a-matching-hash"
            (base / "predictions.jsonl").write_text(json.dumps(record) + "\n")
            clip = SimpleNamespace(clip_id="clip", source_id=1,
                                   frames=np.zeros((4, 4, 6, 3), dtype=np.uint8), brief={},
                                   annotation=record["annotation"])
            with patch("briefguard.data.iter_clips", return_value=iter([clip])):
                with self.assertRaisesRegex(ValueError, "differ from run"):
                    export_demo(base, base / "viewer", {})

    def test_gzip_predictions_are_read(self):
        from briefguard.demo_export import _read_rows
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            record = row("clip", "uniform", False, False)
            (path / "predictions.jsonl.gz").write_bytes(gzip.compress((json.dumps(record) + "\n").encode()))
            rows, source = _read_rows(path)
            self.assertEqual(rows, [record])
            self.assertEqual(source.name, "predictions.jsonl.gz")


if __name__ == "__main__":
    unittest.main()

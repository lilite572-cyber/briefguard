import copy
import json
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch
from pathlib import Path

from briefguard.metrics import score, clustered_intervals
from briefguard.runner import atomic_json, validate_config, run, freeze, read_rows


def row(source, clip, truth, pred, hit=False):
    return {"source_id": source, "clip_id": clip, "annotation": {"violated": truth},
            "prediction": {"violated": pred, "status": "indeterminate" if pred is None else "fail" if pred else "pass"},
            "sampling_hit": hit}


class MetricsTests(unittest.TestCase):
    def test_denominators_and_abstentions(self):
        rows = [row(1, "a", True, True, True), row(1, "b", True, False), row(1, "c", True, None),
                row(1, "d", False, True), row(1, "e", False, False), row(1, "f", None, None)]
        s = score(rows)
        self.assertAlmostEqual(s["recall"], 1 / 3)
        self.assertAlmostEqual(s["miss_rate"], 2 / 3)
        self.assertAlmostEqual(s["false_approval_rate"], 1 / 3)
        self.assertEqual(s["false_alarm_rate"], .5)
        self.assertEqual(s["approval_contamination"], .5)
        self.assertEqual(s["unknown_gt"], 1)
        self.assertEqual(s["abstention_rate"], 2 / 6)

    def test_paired_bootstrap_identity_and_clustering(self):
        a = [row(i, f"{i}-{j}", True, i % 2 == 0, True) for i in range(8) for j in range(4)]
        result = clustered_intervals({"uniform": a, "change": copy.deepcopy(a), "adaptive": copy.deepcopy(a)}, 300, 10)
        self.assertEqual(result["source_clusters"], 8)
        self.assertEqual(result["recall_differences"]["adaptive_minus_uniform"]["ci95"], [0.0, 0.0])
        self.assertEqual(result, clustered_intervals({"uniform": a, "change": a, "adaptive": a}, 300, 10))

    def test_reject_unpaired_data(self):
        a = [row(1, "a", True, True)]
        with self.assertRaises(ValueError):
            clustered_intervals({"uniform": a, "adaptive": [row(1, "b", True, True)]})

    def test_split_leakage(self):
        config = json.loads(Path("configs/study.json").read_text())
        validate_config(config)
        config["test_start"] = config["pilot_sources"][0]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_atomic_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "a.json"
            atomic_json(path, {"x": 1})
            self.assertEqual(json.loads(path.read_text()), {"x": 1})
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_resume_compressed_evidence_and_freeze_guard(self):
        config = json.loads(Path("configs/study.json").read_text())
        config.update({"pilot_sources": [900010, 900011], "dev_sources": [900020, 900021],
                       "test_start": 900100, "test_min_sources": 2, "test_max_sources": 2,
                       "n_frames": 96, "durations": [2], "budgets": [2], "primary_budget": 2,
                       "bootstrap_resamples": 20})
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            folder = Path(d) / "pilot"
            first = run(config, "pilot", folder)
            original = read_rows(folder / "predictions.jsonl")
            (folder / "predictions.jsonl").unlink()
            with patch("briefguard.runner.verify", side_effect=AssertionError("Cache should avoid inference")):
                resumed = run(config, "pilot", folder)
            self.assertEqual(resumed["fresh_units"], 0)
            self.assertEqual(resumed["reused_units"], first["rows"])
            self.assertEqual(original, read_rows(folder / "predictions.jsonl.gz"))
            frozen_path = Path(d) / "frozen.json"
            frozen = freeze(config, folder, frozen_path)
            self.assertEqual(frozen["test_source_ids"], [900100, 900101])
            with self.assertRaises(ValueError):
                freeze(config, folder, frozen_path)
            drift = copy.deepcopy(config)
            drift["sampling"]["noise_floor"] += 1
            with self.assertRaisesRegex(ValueError, "drift"):
                run(drift, "test", Path(d) / "test", frozen_path)


if __name__ == "__main__":
    unittest.main()

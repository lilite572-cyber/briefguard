"""Regression checks for incomplete evidence and optimized-Python comparison."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from briefguard.evidence import validate_completed_run, validate_saved_summary
from briefguard.metrics import summarize
from briefguard.runner import digest, read_rows

ROOT = Path(__file__).resolve().parents[1]


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = ROOT / "results" / "test"
        cls.meta = json.loads((run / "metadata.json").read_text())
        source = cls.meta["identity"]["source_ids"][0]
        cls.meta["identity"]["source_ids"] = [source]
        cls.meta["run_id"] = digest(cls.meta["identity"])[:16]
        cls.rows = [r for r in read_rows(run / "predictions.jsonl") if r["source_id"] == source]
        cls.manifest = [r for r in read_rows(run / "manifest.jsonl") if r["source_id"] == source]
        cls.meta["rows"] = len(cls.rows)
        for row in cls.rows:
            row["run_id"] = cls.meta["run_id"]
            row["unit_id"] = digest([row["run_id"], row["clip_id"], row["pixels_sha256"],
                                     digest(row["brief"]), row["method"], row["budget"]])

    def write_run(self, path, mutate=None):
        path.mkdir(parents=True, exist_ok=True)
        meta, rows, manifest = copy.deepcopy((self.meta, self.rows, self.manifest))
        if mutate:
            mutate(meta, rows, manifest)
        (path / "metadata.json").write_text(json.dumps(meta))
        for name, values in (("predictions", rows), ("manifest", manifest)):
            (path / f"{name}.jsonl").write_text("".join(json.dumps(v) + "\n" for v in values))
        return path

    def test_complete_matrix_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            meta, rows = validate_completed_run(self.write_run(Path(folder)))
            self.assertEqual(meta["rows"], 234)
            self.assertEqual(len(rows), 234)

    def test_truncation_even_with_adjusted_metadata_rejected(self):
        def truncate(meta, rows, manifest):
            rows.pop()
            meta["rows"] = len(rows)
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_run(Path(folder), truncate)
            with self.assertRaisesRegex(ValueError, "matrix"):
                validate_completed_run(path)
            result = subprocess.run([sys.executable, "-m", "briefguard", "report", "--run", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((path / "summary.json").exists())

    def test_duplicate_unit_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_run(Path(folder), lambda m, r, f: r.__setitem__(1, copy.deepcopy(r[0])))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                validate_completed_run(path)

    def test_manifest_drift_rejected(self):
        mutations = [lambda m, r, f: f.pop(),
                     lambda m, r, f: r[0]["brief"].__setitem__("target_rgb", [0, 0, 0]),
                     lambda m, r, f: r[0]["annotation"].__setitem__("human_audit", "invented"),
                     lambda m, r, f: r[0].__setitem__("pixels_sha256", "bad")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    validate_completed_run(self.write_run(Path(folder), mutate))

    def test_optimized_comparison_still_rejects_different_predictions(self):
        def change_prediction(meta, rows, manifest):
            rows[0]["prediction"]["api_cost_usd"] = 1
        with tempfile.TemporaryDirectory() as folder:
            left = self.write_run(Path(folder) / "left")
            right = self.write_run(Path(folder) / "right", change_prediction)
            validate_completed_run(left)
            validate_completed_run(right)
            result = subprocess.run([sys.executable, "-O", str(ROOT / "scripts/compare_runs.py"), str(left), str(right)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Evidence mismatch", result.stderr)
            self.assertNotIn('"exact_evidence_match": true', result.stdout)

    def test_cli_missing_input_has_concise_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-m", "briefguard", "check", "--run", folder],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("briefguard:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_stale_summary_is_rejected_before_demo_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_run(Path(folder))
            meta, rows = validate_completed_run(path)
            config = meta["identity"]["config"]
            summary = summarize(rows, config)
            summary_path = path / "summary.json"
            summary_path.write_text(json.dumps(summary))
            validate_saved_summary(path, rows, config)
            summary["hypothesis_supported"] = not summary["hypothesis_supported"]
            summary_path.write_text(json.dumps(summary))
            before = summary_path.read_bytes()
            viewer = path / "viewer"
            result = subprocess.run([sys.executable, "-m", "briefguard", "demo", "--run", str(path), "--out", str(viewer)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Saved summary differs", result.stderr)
            self.assertFalse(viewer.exists())
            self.assertEqual(summary_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

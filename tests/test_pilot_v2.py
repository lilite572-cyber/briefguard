"""Versioned pilot compatibility checks; temporary media/labels are test fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from briefguard import pilot, pilot_v2


class PilotVersionTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fixture.gif"
        frames = [Image.fromarray(np.full((24, 24, 3), i * 15, dtype=np.uint8)) for i in range(12)]
        frames[0].save(self.source, save_all=True, append_images=frames[1:], duration=500, loop=0)

    def fixture_protocol(self):
        # Explicitly altered test-only source identity, never a NASA research packet.
        config = json.loads(pilot_v2.CONFIG.read_text())
        config["natural_source"]["expected_sha256"] = pilot.digest(self.source.read_bytes())
        path = self.root / "fixture-config.json"
        path.write_text(json.dumps(config))
        return path, config

    def test_original_minimum_still_rejects_twelve_frames(self):
        with self.assertRaisesRegex(ValueError, "too few frames"):
            pilot.prepare(self.root / "v1", self.source)

    def test_version_two_requires_pinned_bytes(self):
        with self.assertRaisesRegex(ValueError, "pinned official NASA"):
            pilot_v2.prepare(self.root / "v2", self.source)
        self.assertFalse((self.root / "v2/input_freeze.json").exists())

    def test_v2_preserves_twelve_frames_and_original_interval_formulas(self):
        path, config = self.fixture_protocol()
        with patch.object(pilot_v2, "CONFIG", path):
            plan = pilot_v2.prepare(self.root / "v2", self.source)
            self.assertEqual(plan, pilot_v2.validate_preparation(self.root / "v2"))
            self.assertTrue(plan["complete_data"])
            self.assertEqual(18, len(plan["jobs"]))
            natural = [case for case in plan["cases"] if case["origin"] == "natural_source_injected"]
            self.assertEqual(3, len(natural))
            self.assertEqual(1, len({case["source_id"] for case in natural}))
            for case in natural:
                self.assertEqual([0.5] * 12, case["durations"])
                self.assertEqual(12, len(np.load(self.root / "v2" / (case["case_id"] + ".npy"))))
                if case["clip_id"].endswith("blackout"):
                    self.assertEqual((4, 6), (case["annotation"]["start_frame"], case["annotation"]["end_frame"]))
                if case["clip_id"].endswith("magenta_patch"):
                    self.assertEqual((6, 12), (case["annotation"]["start_frame"], case["annotation"]["end_frame"]))
            with self.assertRaisesRegex(ValueError, "Human labels"):
                pilot_v2.run(self.root / "v2", approved=True, transport=lambda *args: self.fail("No network"))
        with self.assertRaisesRegex(ValueError, "budget/model"):
            pilot.validate_preparation(self.root / "v2")

    def test_protocol_freezes_are_not_interchangeable(self):
        old = self.root / "old"
        new = self.root / "new"
        pilot.prepare(old)
        pilot_v2.prepare(new)
        pilot.validate_preparation(old)
        pilot_v2.validate_preparation(new)
        self.assertNotEqual(pilot.code_hashes(), pilot_v2.code_hashes())
        with self.assertRaisesRegex(ValueError, "budget/model"):
            pilot_v2.validate_preparation(old)
        with self.assertRaisesRegex(ValueError, "budget/model"):
            pilot.validate_preparation(new)
        lock = json.loads((new / "input_freeze.json").read_text())
        self.assertIn("briefguard/pilot_v2.py", lock["code_hashes"])
        self.assertIn("briefguard/pilot.py", lock["code_hashes"])

    def test_cli_default_is_v1_and_v2_run_selects_v2_validator(self):
        default = self.root / "default"
        command = [sys.executable, "-m", "briefguard", "pilot"]
        result = subprocess.run(command + ["prepare", "--out", str(default)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("v1", json.loads(result.stdout)["protocol"])
        self.assertEqual("briefguard-vlm-exploratory-v1", json.loads((default / "plan.json").read_text())["config"]["study_id"])
        newer = self.root / "v2"
        result = subprocess.run(command + ["prepare", "--protocol", "v2", "--out", str(newer)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        result = subprocess.run(command + ["check", "--protocol", "v2", "--directory", str(newer)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        result = subprocess.run(command + ["run", "--protocol", "v2", "--directory", str(newer), "--approve-openai-gpt41mini-usd050"], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("Natural source is missing", result.stderr)
        self.assertFalse((newer / "api").exists())


if __name__ == "__main__":
    unittest.main()

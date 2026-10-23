"""Synthetic test fixtures below are NOT human annotations or audit evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_human_review import prepare, digest, select_cases
from score_human_review import score

ROOT = Path(__file__).resolve().parents[1]


class HumanReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "audit"
        cls.summary = prepare(ROOT / "results/dev", cls.out)
        cls.key = json.loads((cls.out / "evaluator_key.json").read_text())
        cls.blank = json.loads((cls.out / "reviewer/blank_labels.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def unknown_fixture(self):
        """Parser-only fixture; deliberately no inferred ground truth."""
        s = copy.deepcopy(self.blank)
        s.update(reviewer_id="UNIT_TEST_NOT_A_HUMAN", human_attestation=True)
        for r in s["labels"]:
            r.update(decision="unknown", notes="Unit test fixture")
        return s

    def test_blind_payload_and_assets(self):
        import hashlib
        from PIL import Image
        import numpy as np
        pixel_hashes = {c["case_id"]: c["pixels_sha256"] for c in self.key["cases"]}
        public = self.key["public_payload"]
        self.assertEqual(16, len(public["cases"]))
        forbidden = {"annotation", "source_id", "clip_id", "prediction", "selected_indices", "severity", "motion", "sampling_hit"}
        for case in public["cases"]:
            self.assertFalse(forbidden & case.keys())
            path = self.out / "reviewer" / case["asset"]
            self.assertEqual(case["asset_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            with Image.open(path) as im:
                self.assertEqual(im.size, (case["width"]*12, case["height"]*8))
                w, h = case["width"], case["height"]
                frames = np.stack([np.asarray(im.crop((i%12*w, i//12*h, (i%12+1)*w, (i//12+1)*h))) for i in range(case["frames"])])
                self.assertEqual(pixel_hashes[case["case_id"]], hashlib.sha256(frames.tobytes()).hexdigest())
        self.assertEqual({"dev"}, {self.key["split"]})
        self.assertEqual({0, 2, 6, 12}, {r["annotation"]["duration_frames"] for r in self.key["cases"]})
        self.assertEqual({"none", "clear", "subtle"}, {r["annotation"]["severity"] for r in self.key["cases"]})

    def test_blank_incomplete_duplicate_invalid_refused(self):
        with self.assertRaises(ValueError): score(self.key, self.blank)
        for mutation in [lambda s: s["labels"].pop(), lambda s: s["labels"].__setitem__(0,s["labels"][1]),
                         lambda s: s["labels"][0].update(decision="pass"),
                         lambda s: s["labels"][0].update(notes=""),
                         lambda s: s.update(dataset_id="wrong"),
                         lambda s: s.update(reviewer_role="AI")]:
            s = self.unknown_fixture(); mutation(s)
            with self.assertRaises(ValueError): score(self.key, s)

    def test_unknown_excluded_and_groups_reported(self):
        result = score(self.key, self.unknown_fixture())
        self.assertEqual(16,result["n_unknown"])
        self.assertEqual(0,result["known_denominator"])
        self.assertEqual(0,result["presence_agreement_count"])
        self.assertEqual(len({c["source_id"] for c in self.key["cases"]}), result["n_source_groups"])

    def test_half_open_intervals_and_booleans_refused(self):
        for start,end in [(4,4),(-1,2),(0,97),(True,3),(1.5,3)]:
            s=self.unknown_fixture();s["labels"][0].update(decision="violation",violation_type="forbidden_patch",start_frame=start,end_frame=end)
            with self.assertRaises(ValueError):score(self.key,s)
        s=self.unknown_fixture();s["labels"][0].update(decision="violation",violation_type="forbidden_patch",start_frame=0,end_frame=96)
        self.assertEqual(1,score(self.key,s)["known_denominator"])

    def test_overwrite_and_test_split_refused(self):
        with self.assertRaises(ValueError):prepare(ROOT / "results/dev", self.out)
        with self.assertRaises(ValueError):prepare(ROOT / "results/test", self.out / "test")

    def test_truncated_manifest_refused(self):
        import gzip
        run = Path(self.temp.name) / "truncated"
        run.mkdir(exist_ok=True)
        (run / "metadata.json").write_bytes((ROOT / "results/dev/metadata.json").read_bytes())
        lines = gzip.decompress((ROOT / "results/dev/manifest.jsonl.gz").read_bytes()).splitlines()
        (run / "manifest.jsonl.gz").write_bytes(gzip.compress(b"\n".join(lines[:-1]) + b"\n"))
        with self.assertRaises(ValueError): prepare(run, self.out / "truncated")

    def test_payload_integrity(self):
        key=copy.deepcopy(self.key);key["public_payload"]["cases"][0]["frames"]=100
        with self.assertRaises(ValueError):score(key,self.unknown_fixture())

if __name__ == "__main__":
    unittest.main()

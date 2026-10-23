"""Corruption checks for the separately executable static replay audit."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from scripts.check_demo import check_demo


ROOT = Path(__file__).resolve().parents[1]


class ReplayAssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.demo = Path(self.temporary.name) / "demo"
        shutil.copytree(ROOT / "demo", self.demo)
        self.config = json.loads((ROOT / "configs/study.json").read_text())
        self.payload = json.loads((self.demo / "data.json").read_text())

    def write_payload(self):
        data = json.dumps(self.payload)
        (self.demo / "data.json").write_text(data)
        (self.demo / "data.js").write_text("window.BRIEFGUARD_DATA = " + data + ";\n")

    def test_stale_script_payload_is_rejected(self):
        self.payload["human_audit"] = "fabricated"
        (self.demo / "data.json").write_text(json.dumps(self.payload))
        with self.assertRaisesRegex(ValueError, "data.js differs"):
            check_demo(self.demo, ROOT / "results/test", self.config)

    def test_altered_prediction_is_rejected_even_when_json_and_js_agree(self):
        case = self.payload["clips"][0]
        row = case["methods"]["uniform"]
        row["prediction"]["violated"] = not row["prediction"]["violated"]
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "evidence differs"):
            check_demo(self.demo, ROOT / "results/test", self.config)

    def test_one_changed_thumbnail_pixel_is_rejected(self):
        url = next(iter(self.payload["clips"][0]["frame_urls"].values()))
        path = self.demo / url
        with Image.open(path) as source:
            changed = source.copy()
        pixel = changed.getpixel((0, 0))
        changed.putpixel((0, 0), ((pixel[0] + 1) % 256, pixel[1], pixel[2]))
        changed.save(path)
        with self.assertRaisesRegex(ValueError, "Frame image differs"):
            check_demo(self.demo, ROOT / "results/test", self.config)


if __name__ == "__main__":
    unittest.main()

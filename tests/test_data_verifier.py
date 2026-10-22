import unittest

import numpy as np

from briefguard.data import iter_clips, pixel_box
from briefguard.verifier import verify


class DataVerifierTests(unittest.TestCase):
    # Unit fixture IDs are not used by pilot, development or held-out evaluation.
    def test_siblings_and_reproducibility(self):
        first = list(iter_clips(900001))
        second = list(iter_clips(900001))
        self.assertEqual(len(first), 26)
        self.assertEqual(sum(not c.annotation["violated"] for c in first), 2)
        for a, b in zip(first, second):
            self.assertEqual(a.annotation, b.annotation)
            np.testing.assert_array_equal(a.frames, b.frames)
            self.assertEqual(a.frames.dtype, np.uint8)
            self.assertEqual(a.frames.shape, (96, 72, 128, 3))

    def test_half_open_annotation_matches_pixel_changes(self):
        clips = list(iter_clips(900002))
        clean = {c.annotation["motion"]: c for c in clips if not c.annotation["violated"]}
        for clip in clips:
            if not clip.annotation["violated"]:
                continue
            differs = np.any(clip.frames != clean[clip.annotation["motion"]].frames, axis=(1, 2, 3))
            expected = np.zeros(len(clip.frames), dtype=bool)
            expected[clip.annotation["start_frame"]:clip.annotation["end_frame"]] = True
            np.testing.assert_array_equal(differs, expected)

    def test_clean_and_missing_product(self):
        for clip in iter_clips(900003):
            annotation = clip.annotation
            if not annotation["violated"]:
                result = verify(clip.frames[::12], list(range(0, 96, 12)), clip.brief)
                self.assertEqual(result["status"], "pass")
            elif annotation["violation_type"] == "missing_product":
                start, end = annotation["start_frame"], annotation["end_frame"]
                result = verify(clip.frames[[start]], [start], clip.brief)
                self.assertTrue(result["violated"])
                # The exit boundary itself is clean, despite a large pixel change.
                self.assertFalse(verify(clip.frames[[end]], [end], clip.brief)["violated"])

    def test_visible_subtle_events_can_escape_verifier(self):
        clips = list(iter_clips(900004))
        subtle = [c for c in clips if c.annotation["severity"] == "subtle"]
        self.assertTrue(subtle)
        for clip in subtle:
            t = clip.annotation["start_frame"]
            self.assertFalse(verify(clip.frames[[t]], [t], clip.brief)["violated"])

    def test_fail_closed_invalid_inputs(self):
        clip = next(iter_clips(900005))
        self.assertEqual(verify(clip.frames[:0], [], clip.brief)["status"], "indeterminate")
        self.assertEqual(verify(clip.frames[:2], [1, 1], clip.brief)["status"], "indeterminate")
        invalid = dict(clip.brief, label_roi=[0, 0, 0, 1])
        self.assertEqual(verify(clip.frames[:1], [0], invalid)["status"], "indeterminate")
        with self.assertRaises(ValueError):
            pixel_box([0, 0, 2, 1], 128, 72)
        with self.assertRaises(ValueError):
            list(iter_clips(1, {"n_frames": 32, "durations": [31]}))


if __name__ == "__main__":
    unittest.main()

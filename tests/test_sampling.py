import unittest
from unittest.mock import patch

import numpy as np

from briefguard.sampling import extract_features, select_frames


class SamplingTests(unittest.TestCase):
    def test_exact_unique_budgets_and_reproducibility(self):
        rng = np.random.default_rng(821)
        for n in (1, 2, 7, 31):
            frames = rng.integers(0, 256, (n, 18, 32, 3), dtype=np.uint8)
            features = extract_features(frames)
            for k in (1, 2, 8, 40):
                for method in ("uniform", "change", "adaptive"):
                    indices = select_frames(method, n, k, features)
                    self.assertEqual(len(indices), min(n, k))
                    self.assertEqual(indices, sorted(set(indices)))
                    self.assertTrue(all(0 <= i < n for i in indices))
                    self.assertEqual(indices, select_frames(method, n, k, features))

    def test_uniform_segment_midpoints(self):
        self.assertEqual(select_frames("uniform", 96, 8), [6, 18, 30, 42, 54, 66, 78, 90])
        self.assertEqual(select_frames("uniform", 0, 8), [])

    def test_no_motion_remains_well_defined(self):
        features = extract_features(np.full((96, 72, 128, 3), 100, dtype=np.uint8))
        for name in ("global_change", "local_novelty", "local_change"):
            np.testing.assert_array_equal(features[name], np.zeros(96))
        for method in ("uniform", "change", "adaptive"):
            self.assertEqual(len(set(select_frames(method, 96, 8, features))), 8)

    def test_change_scores_transition_at_current_frame(self):
        # An exit frame has high change despite being clean. Do not shift its
        # timestamp backwards or interpret every high score as a GT event hit.
        frames = np.zeros((8, 8, 8, 3), dtype=np.uint8)
        frames[3:5] = 100
        features = extract_features(frames)
        self.assertEqual(np.flatnonzero(features["global_change"]).tolist(), [3, 5])
        self.assertEqual(features["local_novelty"][5], 0)
        self.assertGreater(features["local_novelty"][3], 0)

    def test_localized_transient_is_visible_in_features(self):
        frames = np.full((16, 18, 32, 3), 100, dtype=np.uint8)
        frames[5:7, 5:8, 15:18] = 125
        features = extract_features(frames)
        self.assertGreater(features["local_novelty"][5], 0)
        self.assertEqual(features["local_novelty"][0], 0)

    def test_prepass_accounting_and_nondivisible_resize(self):
        for shape in ((3, 72, 128, 3), (3, 73, 129, 3)):
            features = extract_features(np.zeros(shape, dtype=np.uint8))
            self.assertEqual(features["metadata"]["frames_examined"], 3)
            self.assertEqual(features["metadata"]["source_pixels_read"], int(np.prod(shape[:3])))
            self.assertEqual(features["metadata"]["low_resolution_pixels"], 3 * 18 * 32)

    def test_does_not_mutate_input_or_scores(self):
        frames = np.arange(12 * 18 * 32 * 3, dtype=np.uint8).reshape(12, 18, 32, 3)
        original = frames.copy()
        features = extract_features(frames)
        before = {name: value.copy() for name, value in features.items() if isinstance(value, np.ndarray)}
        for method in ("uniform", "change", "adaptive"):
            select_frames(method, 12, 3, features)
        np.testing.assert_array_equal(frames, original)
        for name in before:
            np.testing.assert_array_equal(features[name], before[name])

    def test_global_mode_skips_adaptive_feature_work(self):
        frames = np.arange(12 * 18 * 32 * 3, dtype=np.uint8).reshape(12, 18, 32, 3)
        full = extract_features(frames)
        with patch("briefguard.sampling.np.median", side_effect=AssertionError("unexpected adaptive work")), patch("briefguard.sampling.np.quantile", side_effect=AssertionError("unexpected adaptive work")):
            global_only = extract_features(frames, {"feature_mode": "global"})
        np.testing.assert_array_equal(global_only["global_change"], full["global_change"])
        self.assertNotIn("local_novelty", global_only)
        self.assertNotIn("local_change", global_only)
        self.assertEqual(global_only["metadata"]["feature_mode"], "global")
        self.assertEqual(select_frames("change", 12, 4, full), select_frames("change", 12, 4, global_only))

    def test_invalid_inputs(self):
        for n, k in ((-1, 8), (10, 0), (10, -1), (10.5, 3), (10, True)):
            with self.assertRaises(ValueError):
                select_frames("uniform", n, k)
        with self.assertRaises(ValueError):
            select_frames("unknown", 10, 3)
        with self.assertRaises(ValueError):
            select_frames("change", 10, 3)
        for scores in ([0, 1], [float("nan")] * 10, [-1] * 10):
            with self.assertRaises(ValueError):
                select_frames("change", 10, 3, {"global_change": scores})
        for frames in (np.zeros((0, 18, 32, 3), dtype=np.uint8), np.zeros((8, 18, 32, 3)), np.zeros((8, 18, 32), dtype=np.uint8)):
            with self.assertRaises(ValueError):
                extract_features(frames)
        with self.assertRaises(ValueError):
            extract_features(np.zeros((3, 18, 32, 3), dtype=np.uint8), {"noise_floor": 0})


if __name__ == "__main__":
    unittest.main()

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from PIL import Image

from briefguard.video import VideoLoadError, load_video


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_npz_preserves_frames_indices_and_timing(self):
        path = self.root / "clip.npz"
        frames = np.zeros((3, 12, 16, 3), dtype=np.uint8)
        frames[1] = 80
        frames[2] = 160
        np.savez_compressed(path, frames=frames, fps=np.array(24.0))
        video = load_video(path, width=8, height=6)
        self.assertEqual(video.frames.shape, (3, 6, 8, 3))
        self.assertEqual(video.original_indices, [0, 1, 2])
        np.testing.assert_allclose(video.timestamps_seconds, [0, 1 / 24, 2 / 24])
        self.assertEqual(video.fps, 24)
        self.assertEqual(int(video.frames[1, 0, 0, 0]), 80)
        self.assertFalse(video.metadata["truncated"])

    def test_variable_timing_gif(self):
        path = self.root / "variable.gif"
        images = [Image.new("RGB", (16, 12), color) for color in ("red", "green", "blue")]
        images[0].save(path, save_all=True, append_images=images[1:], duration=[40, 80, 120], loop=0)
        video = load_video(path, width=8, height=6)
        self.assertIsNone(video.fps)
        self.assertEqual(video.original_indices, [0, 1, 2])
        np.testing.assert_allclose(video.timestamps_seconds, [0, .04, .12])
        np.testing.assert_allclose(video.durations_seconds, [.04, .08, .12])
        self.assertTrue(video.metadata["variable_frame_rate"])
        self.assertEqual(video.frames[0, 0, 0].tolist(), [255, 0, 0])

    def test_png_natural_order_and_explicit_rate(self):
        directory = self.root / "frames"
        directory.mkdir()
        for index in (10, 2, 1):
            Image.new("RGB", (16, 12), (index, index, index)).save(directory / f"frame{index}.png")
        with self.assertRaisesRegex(VideoLoadError, "fps"):
            load_video(directory)
        video = load_video(directory, fps=10, width=8, height=6)
        self.assertEqual(video.frames[:, 0, 0, 0].tolist(), [1, 2, 10])
        self.assertEqual(video.metadata["source_filenames"], ["frame1.png", "frame2.png", "frame10.png"])

    def test_frame_pixel_and_memory_limits_reject(self):
        path = self.root / "clip.npz"
        np.savez_compressed(path, frames=np.zeros((3, 12, 16, 3), dtype=np.uint8), fps=np.array(24))
        for options in ({"max_frames": 2}, {"max_pixels": 100}, {"max_bytes": 100}):
            with self.assertRaises(VideoLoadError):
                load_video(path, width=8, height=6, **options)

    def test_rejects_object_arrays_before_np_load(self):
        path = self.root / "object.npz"
        np.savez_compressed(path, frames=np.array([{"arbitrary": "object"}], dtype=object), fps=np.array(24))
        with patch("briefguard.video.np.load", side_effect=AssertionError("np.load must not be called")):
            with self.assertRaisesRegex(VideoLoadError, "object arrays"):
                load_video(path)

    def test_header_shape_bomb_rejected_before_np_load(self):
        path = self.root / "bomb.npz"
        fake = io.BytesIO()
        np.lib.format.write_array_header_1_0(fake, {"descr": "|u1", "fortran_order": False, "shape": (10**9, 72, 128, 3)})
        fps = io.BytesIO()
        np.save(fps, np.array(24))
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("frames.npy", fake.getvalue())
            archive.writestr("fps.npy", fps.getvalue())
        with patch("briefguard.video.np.load", side_effect=AssertionError("np.load must not be called")):
            with self.assertRaisesRegex(VideoLoadError, "header and member size"):
                load_video(path)

    def test_npz_members_and_fps_validation(self):
        path = self.root / "bad.npz"
        frames = np.zeros((2, 12, 16, 3), dtype=np.uint8)
        for fps in (float("nan"), -1, 0, True):
            np.savez_compressed(path, frames=frames, fps=np.array(fps))
            with self.assertRaises(VideoLoadError):
                load_video(path)
        np.savez_compressed(path, frames=frames, fps=np.array(24), extra=np.array([1]))
        with self.assertRaisesRegex(VideoLoadError, "exactly two"):
            load_video(path)

    def test_gif_missing_timing_and_too_many_frames(self):
        path = self.root / "clip.gif"
        images = [Image.new("RGB", (16, 12), color) for color in ("red", "blue")]
        images[0].save(path, save_all=True, append_images=images[1:])
        with self.assertRaisesRegex(VideoLoadError, "positive duration"):
            load_video(path)
        images[0].save(path, save_all=True, append_images=images[1:], duration=40)
        with self.assertRaisesRegex(VideoLoadError, "max_frames"):
            load_video(path, max_frames=1)
        with self.assertRaisesRegex(VideoLoadError, "retain their source timing"):
            load_video(path, fps=25)

    def test_actionable_unsupported_and_corrupt_errors(self):
        path = self.root / "clip.mp4"
        path.write_bytes(b"not a real video")
        with self.assertRaisesRegex(VideoLoadError, "external ffmpeg"):
            load_video(path)
        path = self.root / "broken.gif"
        path.write_bytes(b"broken")
        with self.assertRaisesRegex(VideoLoadError, "cannot decode"):
            load_video(path)
        with self.assertRaisesRegex(VideoLoadError, "does not exist"):
            load_video(self.root / "missing.npz")


if __name__ == "__main__":
    unittest.main()

"""Deterministic, independently authored fixed-template video stress test.

The generator owns annotations. Selectors and verifiers must receive only pixels
and the public brief, never a Clip or its annotation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image

GENERATOR_VERSION = "template-ad-v1"
VIOLATION_TYPES = ("missing_product", "wrong_color", "label_corruption", "forbidden_patch")
MOTIONS = ("quiet", "distractor")


@dataclass
class Clip:
    clip_id: str
    source_id: int
    frames: np.ndarray
    brief: dict
    annotation: dict


def _rng(source_id: int, stream: int = 0) -> np.random.Generator:
    if not isinstance(source_id, int) or source_id < 0:
        raise ValueError("source_id must be a nonnegative integer")
    return np.random.default_rng(np.random.SeedSequence([20261022, source_id, stream]))


def _normalized_box(box: tuple[int, int, int, int], width: int, height: int) -> list[float]:
    x0, y0, x1, y1 = box
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def pixel_box(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    """Convert public normalized [left, top, right, bottom] to half-open pixels."""
    if len(box) != 4 or not all(np.isfinite(box)):
        raise ValueError("ROI must contain four finite normalized coordinates")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("ROI must be nonempty and within the frame")
    result = (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
    if result[0] == result[2] or result[1] == result[3]:
        raise ValueError("ROI is empty at this image resolution")
    return result


def _logo() -> np.ndarray:
    """An original bitmap of the fictional word NOVA; no font asset dependency."""
    letters = [
        ["101", "111", "111", "111", "101"],
        ["111", "101", "101", "101", "111"],
        ["101", "101", "101", "101", "010"],
        ["010", "101", "111", "101", "101"],
    ]
    return np.array([[int(c) for c in "0".join(letter[row] for letter in letters)]
                     for row in range(5)], dtype=np.uint8)


def _parameters(config: dict) -> tuple[int, int, int, float, tuple[int, ...]]:
    n = int(config.get("n_frames", 96))
    w, h = int(config.get("width", 128)), int(config.get("height", 72))
    fps = float(config.get("fps", 24))
    durations = tuple(int(d) for d in config.get("durations", [2, 6, 12]))
    if not (32 <= n <= 600 and 96 <= w <= 1024 and 64 <= h <= 576 and 0 < fps <= 120):
        raise ValueError("Unsupported clip dimensions, length or frame rate")
    if not durations or len(set(durations)) != len(durations) or any(d < 1 or d > n - 8 for d in durations):
        raise ValueError("Durations must be unique positive frame counts leaving an onset margin")
    if n * w * h * 3 > 128 * 1024 * 1024:
        raise ValueError("One clip exceeds the 128 MiB raw-pixel memory limit")
    return n, w, h, fps, durations


def iter_clips(source_id: int, config: dict | None = None) -> Iterator[Clip]:
    """Yield clean/altered siblings; all must belong to the same data split.

    Default: 2 motion regimes × (1 clean + 4 types × 3 durations) = 26 clips.
    Frame intervals are authoritative integers, with an exclusive end.
    """
    config = config or {}
    n, w, h, fps, durations = _parameters(config)
    rng = _rng(source_id)
    body_w = int(rng.integers(round(w * .27), round(w * .34) + 1))
    body_h = int(rng.integers(round(h * .57), round(h * .67) + 1))
    x0 = int(rng.integers(round(w * .34), round(w * .43) + 1))
    y0 = int(rng.integers(round(h * .17), round(h * .25) + 1))
    x1, y1 = x0 + body_w, y0 + body_h
    body_box = (x0, y0, x1, y1)
    color_box = (x0 + 3, y1 - max(8, body_h // 4), x1 - 3, y1 - 3)
    logo = _logo()
    lx = x0 + (body_w - logo.shape[1]) // 2
    ly = y0 + body_h // 3
    label_box = (lx, ly, lx + logo.shape[1], ly + logo.shape[0])
    forbidden_box = (w - 19, 5, w - 7, 13)
    palette = np.array([[38, 162, 151], [96, 109, 191], [187, 108, 52]], dtype=np.uint8)
    color = palette[int(rng.integers(len(palette)))].copy()
    white = np.array([240, 242, 235], dtype=np.uint8)
    forbidden = np.array([235, 40, 70], dtype=np.uint8)
    background = np.array([int(rng.integers(18, 38)), int(rng.integers(24, 45)), int(rng.integers(36, 62))])
    brief = {
        "schema_version": "brief-v1", "workload": "fixed-template-synthetic-ad",
        "fps": fps, "frame_size": [w, h],
        "requirements": [
            "The product remains present in its specified region throughout the clip.",
            "The package retains the specified RGB target, allowing the documented benign lighting jitter.",
            "The NOVA bitmap remains unchanged; changing even one bitmap cell is a violation.",
            "No pixels of the forbidden red element may appear in its specified inspection region.",
        ],
        "product_roi": _normalized_box(body_box, w, h),
        "color_roi": _normalized_box(color_box, w, h),
        "label_roi": _normalized_box(label_box, w, h),
        "forbidden_roi": _normalized_box(forbidden_box, w, h),
        "target_rgb": color.tolist(), "label_rgb": white.tolist(),
        "forbidden_rgb": forbidden.tolist(), "label_bitmap": logo.tolist(),
        "benign_channel_jitter_max": 3,
    }
    for motion_index, motion in enumerate(MOTIONS):
        # The motion changes only non-required content. Shared base pixels provide
        # matched controls without exposing a clean counterpart to the algorithms.
        base = np.empty((n, h, w, 3), dtype=np.uint8)
        base[:] = background
        for t in range(n):
            x = 3 + (t * (3 if motion == "distractor" else 1) // (1 if motion == "distractor" else 8)) % max(1, x0 - 23)
            y = 18 + ((t * 2) % max(1, h - 40) if motion == "distractor" else 4)
            base[t, y:y + 17, x:x + 17] = [96, 196, 220] if t % 7 < 4 else [170, 196, 90]
            if motion == "distractor":
                # A flashing benign lower border is deliberately highly salient.
                base[t, h - 5:h - 2, :] = [45 + (t % 5) * 28, 90 + (t % 3) * 40, 120]
        background_frames = base.copy()
        base[:, y0:y1, x0:x1] = color
        base[:, max(0, y0 - 4):y0, x0 + 5:x1 - 5] = [202, 211, 216]
        base[:, ly:ly + 5, lx:lx + 15] = np.where(logo[..., None], white, color)
        # Shared bounded light jitter is applied after edits below. It does not
        # encode the event time and is identically distributed in clean siblings.
        phase = float(rng.uniform(0, np.pi))
        jitter = np.rint(2 * np.sin(np.arange(n) * .21 + phase)).astype(np.int16)
        noise = _rng(source_id, 10 + motion_index).integers(-1, 2, size=(n, h, w, 1), dtype=np.int16)
        variants = [(None, 0)] + [(kind, duration) for kind in VIOLATION_TYPES for duration in durations]
        for variant_index, (kind, duration) in enumerate(variants):
            vrng = _rng(source_id, 100 + motion_index * 100 + variant_index)
            frames = base.copy()
            start = int(vrng.integers(3, n - duration - 2)) if kind else None
            end = start + duration if kind else None
            subtle = bool(vrng.integers(2)) if kind in ("wrong_color", "label_corruption", "forbidden_patch") else False
            severity = "subtle" if subtle else "clear"
            if kind == "missing_product":
                frames[start:end, max(0, y0 - 4):y1, x0:x1] = background_frames[start:end, max(0, y0 - 4):y1, x0:x1]
            elif kind == "wrong_color":
                altered = color.astype(np.int16)
                altered[0] = np.clip(altered[0] + (12 if subtle else 65), 0, 255)
                frames[start:end, y0:y1, x0:x1] = altered.astype(np.uint8)
                frames[start:end, ly:ly + 5, lx:lx + 15] = np.where(logo[..., None], white, altered.astype(np.uint8))
            elif kind == "label_corruption":
                # Remove a random existing stroke, or an entire visible column.
                if subtle:
                    yy, xx = np.argwhere(logo == 1)[int(vrng.integers(int(logo.sum())))]
                    frames[start:end, ly + yy, lx + xx] = color
                else:
                    frames[start:end, ly:ly + 5, lx + 4:lx + 7] = color
            elif kind == "forbidden_patch":
                fx0, fy0, fx1, fy1 = forbidden_box
                if subtle:
                    fx1, fy1 = fx0 + 2, fy0 + 2
                frames[start:end, fy0:fy1, fx0:fx1] = forbidden
            frames = np.clip(frames.astype(np.int16) + jitter[:, None, None, None] + noise, 0, 255).astype(np.uint8)
            annotation = {
                "violated": kind is not None, "violation_type": kind,
                "start_frame": start, "end_frame": end,
                "duration_frames": duration, "duration_seconds": duration / fps,
                "motion": motion, "severity": severity if kind else "none",
                "provenance": "synthetic", "generator_version": GENERATOR_VERSION,
                "human_audit": "pending",
            }
            yield Clip(f"s{source_id:06d}-{motion}-{kind or 'clean'}-{duration}", source_id,
                       frames, brief.copy(), annotation)


def export_gif(clip: Clip, path: str | Path, scale: int = 3) -> None:
    """Preview only: GIF centisecond timing is not the evaluation timebase."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    images = [Image.fromarray(frame).resize((frame.shape[1] * scale, frame.shape[0] * scale), Image.Resampling.NEAREST)
              for frame in clip.frames]
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=round(1000 / clip.brief["fps"]), loop=0, optimize=False)


def save_npz(clip: Clip, path: str | Path) -> None:
    """Portable raw frames; the JSON brief/annotation belong in separate files."""
    np.savez_compressed(path, frames=clip.frames, fps=np.array(clip.brief["fps"]))

"""Deterministic, label-free frame selectors for a fixed checker budget.

All nonuniform selectors inspect a low-resolution view of *every* frame. This
cost must be reported separately from the selected high-resolution frames.
The adaptive heuristic is a reference implementation, not a new algorithm or
an implementation of InfoShot. It uses no brief, ROI, annotations or seed.
"""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np
from PIL import Image

DEFAULTS = {
    "feature_mode": "all",
    "feature_width": 32,
    "feature_height": 18,
    "noise_floor": 6.0,
    "local_quantile": 0.995,
    "anchor_fraction": 0.5,
    "change_weight": 0.25,
    "diversity_floor": 0.25,
    "change_gap_fraction": 0.5,
}


def _config(config):
    result = dict(DEFAULTS)
    if config:
        result.update({k: v for k, v in config.items() if k in DEFAULTS})
    if result["feature_mode"] not in {"all", "global"}:
        raise ValueError("feature_mode must be 'all' or 'global'")
    for key in ("feature_width", "feature_height"):
        if not isinstance(result[key], Integral) or isinstance(result[key], bool) or result[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("noise_floor", "change_weight", "change_gap_fraction"):
        if not math.isfinite(result[key]) or result[key] < 0:
            raise ValueError(f"{key} must be finite and nonnegative")
    if result["noise_floor"] == 0:
        raise ValueError("noise_floor must be positive")
    for key in ("local_quantile", "anchor_fraction", "diversity_floor"):
        if not math.isfinite(result[key]) or not 0 <= result[key] <= 1:
            raise ValueError(f"{key} must lie in [0, 1]")
    return result


def extract_features(frames: np.ndarray, config: dict | None = None) -> dict:
    """Return label-free scores and explicit full-video prepass accounting.

    RGB block averages (or BOX resizing for other dimensions) are the spatial
    features. Global change is mean absolute adjacent difference. At each
    spatial location, novelty is the channel-mean absolute residual from the
    temporal median, divided by max(1.4826 * temporal MAD, noise_floor).
    The local score is the 99.5th percentile across spatial locations. The
    same robust normalization is applied to adjacent differences. No frame
    at t=0 is called a change, and no event interval is inferred here. Set
    feature_mode='global' for the change baseline: it computes no temporal
    medians, robust scores or local quantiles, so its prepass can be timed
    independently without charging it for adaptive-only work.
    """
    cfg = _config(config)
    frames = np.asarray(frames)
    if frames.ndim != 4 or frames.shape[-1] != 3 or frames.dtype != np.uint8:
        raise ValueError("frames must be a uint8 array with shape (T,H,W,3)")
    n, height, width, _ = frames.shape
    if min(n, height, width) < 1:
        raise ValueError("frames must contain at least one nonempty frame")
    fh, fw = min(height, cfg["feature_height"]), min(width, cfg["feature_width"])
    if height % fh == 0 and width % fw == 0:
        # Intermediate float storage is only at low resolution; mean accumulates
        # in float32 directly from the uint8 view of the input.
        low = frames.reshape(n, fh, height // fh, fw, width // fw, 3).mean(axis=(2, 4), dtype=np.float32)
    else:
        low = np.stack([np.asarray(Image.fromarray(frame).resize((fw, fh), Image.Resampling.BOX), dtype=np.float32) for frame in frames])
    adjacent = np.zeros_like(low)
    adjacent[1:] = np.abs(np.diff(low, axis=0))
    result = {
        "global_change": adjacent.mean(axis=(1, 2, 3)),
        "metadata": {
            "frames_examined": n,
            "source_pixels_read": n * height * width,
            "low_resolution_pixels": n * fh * fw,
            "feature_width": fw,
            "feature_height": fh,
            "feature_version": "robust-grid-v1",
            "feature_mode": cfg["feature_mode"],
        },
    }
    if cfg["feature_mode"] == "global":
        return result
    center = np.median(low, axis=0)
    residual = np.abs(low - center)
    scale = np.maximum(1.4826 * np.median(residual, axis=0), cfg["noise_floor"])
    novelty_pixels = np.mean(residual / scale, axis=-1)
    change_center = np.median(adjacent[1:], axis=0) if n > 1 else adjacent[0]
    change_mad = np.median(np.abs(adjacent[1:] - change_center), axis=0) if n > 1 else adjacent[0]
    change_scale = np.maximum(1.4826 * change_mad, cfg["noise_floor"])
    local_change_pixels = np.mean(np.maximum(adjacent - change_center, 0) / change_scale, axis=-1)
    local_change_pixels[0] = 0
    result["local_novelty"] = np.quantile(novelty_pixels.reshape(n, -1), cfg["local_quantile"], axis=1)
    result["local_change"] = np.quantile(local_change_pixels.reshape(n, -1), cfg["local_quantile"], axis=1)
    return result


def _uniform(n: int, k: int) -> list[int]:
    return [((2 * j + 1) * n) // (2 * k) for j in range(k)] if k else []


def _score(features, name, n):
    if features is None or name not in features:
        raise ValueError(f"features must include {name}")
    scores = np.asarray(features[name], dtype=float)
    if scores.shape != (n,) or not np.isfinite(scores).all() or (scores < 0).any():
        raise ValueError(f"{name} must have {n} finite nonnegative scores")
    return scores


def _fill_coverage(selected, n, k):
    if not selected:
        return _uniform(n, k)
    # Maximin temporal coverage. Lowest index breaks every tie deterministically.
    candidates = np.arange(n)
    distance = np.min(np.abs(candidates[:, None] - np.array(selected)[None, :]), axis=1)
    while len(selected) < k:
        index = int(np.argmax(distance))
        selected.append(index)
        distance = np.minimum(distance, np.abs(candidates - index))
    return sorted(selected)


def select_frames(method: str, n_frames: int, budget: int, features: dict | None = None, config: dict | None = None) -> list[int]:
    """Return exactly min(budget, n_frames) sorted unique frame indices.

    change: score descending, index ascending, suppress neighbors closer than
    floor(N/K * change_gap_fraction), then fill by maximin temporal coverage.
    adaptive: ceil(K*anchor_fraction) uniform anchors, then greedy score
    (local_novelty + change_weight*local_change) multiplied by
    diversity_floor + (1-diversity_floor)*min(distance_to_selected/(N/K),1).
    Zero-scored candidates use coverage fill. All scores are computed before
    selection; "adaptive" here means data-dependent greedy budget allocation,
    not a sequential checker-feedback policy.
    """
    if method not in {"uniform", "change", "adaptive"}:
        raise ValueError(f"unknown sampling method: {method}")
    for value, name in ((n_frames, "n_frames"), (budget, "budget")):
        if not isinstance(value, Integral) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
    if n_frames < 0 or budget < 1:
        raise ValueError("n_frames must be nonnegative and budget positive")
    cfg = _config(config)
    n, k = int(n_frames), min(int(budget), int(n_frames))
    if k == 0:
        return []
    if k == n:
        return list(range(n))
    if method == "uniform":
        return _uniform(n, k)
    selected = []
    if method == "change":
        scores = _score(features, "global_change", n)
        gap = max(1, int(n / k * cfg["change_gap_fraction"]))
        for index in np.lexsort((np.arange(n), -scores)):
            index = int(index)
            if scores[index] <= 0:
                break
            if all(abs(index - chosen) >= gap for chosen in selected):
                selected.append(index)
            if len(selected) == k:
                break
        return _fill_coverage(selected, n, k)
    scores = _score(features, "local_novelty", n) + cfg["change_weight"] * _score(features, "local_change", n)
    anchors = min(k, max(1, math.ceil(k * cfg["anchor_fraction"])))
    selected = _uniform(n, anchors)
    candidates = np.arange(n)
    while len(selected) < k:
        distances = np.min(np.abs(candidates[:, None] - np.array(selected)[None, :]), axis=1)
        diversity = cfg["diversity_floor"] + (1 - cfg["diversity_floor"]) * np.minimum(distances / (n / k), 1)
        priority = scores * diversity
        priority[selected] = -1
        index = int(np.argmax(priority))
        if priority[index] <= 0:
            break
        selected.append(index)
    return _fill_coverage(selected, n, k)

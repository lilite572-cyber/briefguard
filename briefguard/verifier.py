"""Pixel-template verifier, deliberately not a semantic VLM or an oracle."""
from __future__ import annotations

import numpy as np

from .data import pixel_box

MODEL_VERSION = "pixel-template-v1"


def verify(frames_selected: np.ndarray, indices: list[int] | np.ndarray, brief: dict) -> dict:
    """Inspect selected pixels only; never accept annotations or a source video.

    Tolerances are fixed engineering choices, not learned confidence estimates.
    Every frame checks all four requirements using the same public brief.
    """
    indices = list(indices)
    base_result = {
        "model_version": MODEL_VERSION,
        "status": "indeterminate", "violated": None, "evidence": [],
        "frames_verified": len(indices), "calls": 1, "api_cost_usd": 0.0,
    }
    if (not isinstance(frames_selected, np.ndarray) or frames_selected.ndim != 4
            or frames_selected.shape[-1] != 3 or len(frames_selected) != len(indices)
            or not len(indices) or frames_selected.dtype != np.uint8):
        return {**base_result, "error": "Expected nonempty uint8 [K,H,W,3] frames and matching indices"}
    if len(set(indices)) != len(indices) or any(not isinstance(i, (int, np.integer)) or i < 0 for i in indices):
        return {**base_result, "error": "Frame indices must be unique nonnegative integers"}
    _, h, w, _ = frames_selected.shape
    try:
        rois = {key: pixel_box(brief[key], w, h) for key in
                ("product_roi", "color_roi", "label_roi", "forbidden_roi")}
        target = np.asarray(brief["target_rgb"], dtype=np.float32)
        label_rgb = np.asarray(brief["label_rgb"], dtype=np.float32)
        forbidden = np.asarray(brief["forbidden_rgb"], dtype=np.float32)
        bitmap = np.asarray(brief["label_bitmap"], dtype=bool)
        if any(value.shape != (3,) or not np.isfinite(value).all() for value in (target, label_rgb, forbidden)):
            raise ValueError("Expected three finite RGB values")
        if list(brief["frame_size"]) != [w, h]:
            raise ValueError("Template size differs from selected frame size")
    except (KeyError, ValueError, TypeError) as exc:
        return {**base_result, "error": str(exc)}
    evidence = []
    per_frame = []
    for frame_index, frame in zip(indices, frames_selected):
        def crop(name: str) -> np.ndarray:
            x0, y0, x1, y1 = rois[name]
            return frame[y0:y1, x0:x1].astype(np.float32)

        body = crop("product_roi")
        # Missing product: most body pixels no longer resemble its original color.
        presence_fraction = float((np.max(np.abs(body - target), axis=-1) < 85).mean())
        color_error = float(np.max(np.abs(np.median(crop("color_roi"), axis=(0, 1)) - target)))
        label = crop("label_roi")
        if label.shape[:2] != bitmap.shape:
            return {**base_result, "error": "Bitmap shape does not match label ROI"}
        observed_bitmap = np.max(np.abs(label - label_rgb), axis=-1) < 40
        mismatch_fraction = float(np.not_equal(observed_bitmap, bitmap).mean())
        forbidden_fraction = float((np.max(np.abs(crop("forbidden_roi") - forbidden), axis=-1) < 20).mean())
        checks = [
            ("product_present", 1.0 - presence_fraction, presence_fraction < .35),
            ("package_color", color_error, color_error > 20),
            ("label_unchanged", mismatch_fraction, mismatch_fraction > .035),
            ("forbidden_element_absent", forbidden_fraction, forbidden_fraction > .08),
        ]
        failed = []
        for requirement, score, is_failure in checks:
            if is_failure:
                failed.append(requirement)
                evidence.append({"frame_index": int(frame_index), "requirement": requirement, "score": round(score, 6)})
        per_frame.append({"frame_index": int(frame_index), "failed_requirements": failed})
    return {**base_result, "status": "fail" if evidence else "pass", "violated": bool(evidence),
            "evidence": evidence, "per_frame": per_frame}

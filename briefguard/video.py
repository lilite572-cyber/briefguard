"""Bounded local video loading with explicit source-frame timing.

Supports RGB uint8 NPZ (frames, fps), naturally ordered PNG directories, and
animated GIF. Spatial resizing does not resample time. Limits reject inputs;
there is no implicit truncation. MP4 requires an explicit external conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral
from pathlib import Path
import re
import zipfile

import numpy as np
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class NormalizedVideo:
    frames: np.ndarray
    fps: float | None
    original_indices: list[int]
    timestamps_seconds: list[float]
    durations_seconds: list[float]
    metadata: dict


class VideoLoadError(ValueError):
    """An invalid, unsupported, or over-budget local input."""


def _positive_int(value, name):
    if not isinstance(value, Integral) or isinstance(value, bool) or value < 1:
        raise VideoLoadError(f"{name} must be a positive integer")
    return int(value)


def _fps(value):
    if isinstance(value, (bool, np.bool_)):
        raise VideoLoadError("fps must be a finite number in (0, 1000]")
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise VideoLoadError("fps must be a finite number in (0, 1000]") from exc
    if not math.isfinite(value) or not 0 < value <= 1000:
        raise VideoLoadError("fps must be a finite number in (0, 1000]")
    return value


def _shape_limit(n, w, h, width, height, max_frames, max_pixels, max_bytes, *, full_source):
    if n < 1 or w < 1 or h < 1:
        raise VideoLoadError("input must contain nonempty frames")
    if n > max_frames:
        raise VideoLoadError(f"input contains {n} frames; max_frames={max_frames}; split it explicitly before loading")
    if w * h > max_pixels:
        raise VideoLoadError(f"source frame has {w*h} pixels; max_pixels={max_pixels}; resize the source before loading")
    # Budget source bytes plus normalized output, not just compressed file size.
    source_bytes = (n if full_source else 1) * w * h * 3
    output_bytes = n * width * height * 3
    if source_bytes + output_bytes > max_bytes:
        raise VideoLoadError(f"decoded source plus output exceeds max_bytes={max_bytes}; reduce dimensions or clip length")


def _read_npy_header(member):
    version = np.lib.format.read_magic(member)
    readers = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}
    if version not in readers:
        raise VideoLoadError(f"unsupported NPY version {version}; export standard numeric NPZ arrays")
    shape, fortran, dtype = readers[version](member, max_header_size=16384)
    if dtype.hasobject:
        raise VideoLoadError("object arrays are forbidden; export RGB uint8 frames and numeric fps")
    return shape, fortran, dtype, member.tell()


def _npz(path, width, height, max_frames, max_pixels, max_bytes):
    if path.stat().st_size > max_bytes:
        raise VideoLoadError("compressed NPZ file exceeds max_bytes")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 2 or {m.filename for m in members} != {"frames.npy", "fps.npy"}:
            raise VideoLoadError("NPZ must contain exactly two arrays: frames and fps")
        if any(m.flag_bits & 1 for m in members):
            raise VideoLoadError("encrypted NPZ members are unsupported")
        if sum(m.file_size for m in members) > max_bytes:
            raise VideoLoadError("uncompressed NPZ members exceed max_bytes; input rejected before array loading")
        header = {}
        for info in members:
            with archive.open(info) as member:
                shape, fortran, dtype, offset = _read_npy_header(member)
            if any(not isinstance(d, Integral) or d < 0 for d in shape):
                raise VideoLoadError("invalid array dimensions")
            decoded_bytes = math.prod(shape) * dtype.itemsize
            if decoded_bytes > max_bytes or offset + decoded_bytes != info.file_size:
                raise VideoLoadError("NPZ array header and member size disagree or exceed max_bytes")
            header[info.filename] = (shape, fortran, dtype)
        shape, _, dtype = header["frames.npy"]
        if len(shape) != 4 or shape[-1] != 3 or dtype != np.dtype("uint8"):
            raise VideoLoadError("frames must be uint8 with shape (T,H,W,3)")
        n, source_h, source_w, _ = shape
        _shape_limit(n, source_w, source_h, width, height, max_frames, max_pixels, max_bytes, full_source=True)
        fps_shape, _, fps_dtype = header["fps.npy"]
        if fps_shape not in ((), (1,)) or fps_dtype.kind not in "fiu":
            raise VideoLoadError("fps must be one real numeric scalar")
    # Headers and declared expanded sizes were checked before np.load. Pickle
    # remains disabled even though the permitted dtypes exclude object arrays.
    with np.load(path, allow_pickle=False, max_header_size=16384) as archive:
        fps = _fps(archive["fps"].item())
        source = archive["frames"]
        frames = np.empty((n, height, width, 3), dtype=np.uint8)
        for i, frame in enumerate(source):
            frames[i] = np.asarray(Image.fromarray(frame).resize((width, height), Image.Resampling.BOX))
    return frames, [1 / fps] * n, [source_w, source_h], {}


def _natural_key(path):
    return [(1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r"(\d+)", path.name)]


def _png_directory(path, width, height, fps, max_frames, max_pixels, max_bytes):
    fps = _fps(fps)
    files = sorted((p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".png"), key=_natural_key)
    if not files:
        raise VideoLoadError("directory contains no PNG frames")
    if len(files) > max_frames:
        raise VideoLoadError(f"directory has {len(files)} frames; max_frames={max_frames}")
    if sum(p.stat().st_size for p in files) > max_bytes:
        raise VideoLoadError("PNG source files exceed max_bytes")
    frames = None
    source_size = None
    for i, file in enumerate(files):
        with Image.open(file) as image:
            if image.format != "PNG":
                raise VideoLoadError(f"{file.name} is not a PNG image")
            if getattr(image, "is_animated", False):
                raise VideoLoadError("animated PNG inside a frame directory is unsupported; extract individual frames")
            w, h = image.size
            _shape_limit(len(files), w, h, width, height, max_frames, max_pixels, max_bytes, full_source=False)
            if source_size is None:
                source_size = [w, h]
                frames = np.empty((len(files), height, width, 3), dtype=np.uint8)
            if source_size != [w, h]:
                raise VideoLoadError("PNG frame dimensions differ; normalize the source sequence explicitly")
            frames[i] = np.asarray(image.convert("RGB").resize((width, height), Image.Resampling.BOX))
    return frames, [1 / fps] * len(files), source_size, {"source_filenames": [p.name for p in files]}


def _gif(path, width, height, max_frames, max_pixels, max_bytes):
    if path.stat().st_size > max_bytes:
        raise VideoLoadError("GIF source file exceeds max_bytes")
    with Image.open(path) as image:
        if image.format != "GIF":
            raise VideoLoadError("input does not contain a GIF")
        w, h = image.size
        # n_frames scans GIF frame metadata; it does not materialize the video.
        n = image.n_frames
        _shape_limit(n, w, h, width, height, max_frames, max_pixels, max_bytes, full_source=False)
        frames = np.empty((n, height, width, 3), dtype=np.uint8)
        durations = []
        for i in range(n):
            image.seek(i)
            duration = float(image.info.get("duration", 0)) / 1000
            if not math.isfinite(duration) or duration <= 0:
                raise VideoLoadError(f"GIF frame {i} has no positive duration; export explicit frame timing")
            durations.append(duration)
            frames[i] = np.asarray(image.convert("RGB").resize((width, height), Image.Resampling.BOX))
    return frames, durations, [w, h], {"looping_ignored": True}


def load_video(path: str | Path, *, width: int = 128, height: int = 72, fps: float | None = None,
               max_frames: int = 600, max_pixels: int = 1280 * 720, max_bytes: int = 256 * 1024 * 1024) -> NormalizedVideo:
    """Load one bounded local clip, preserving source frame indices and time.

    NPZ must contain exactly uint8 ``frames[T,H,W,3]`` and scalar numeric
    ``fps``. PNG directories require explicit ``fps`` and use natural numeric
    filename ordering. GIF timing comes from each frame's duration; ``fps``
    is None when those durations vary. An fps override for timed files is
    rejected. ``metadata['truncated']`` is always False: excessive input is an
    error, never an incomplete video presented as a full compliance check.

    Memory checks bound source array + normalized output (NPZ), or one decoded
    frame + output (streaming images). Decoder/native-library overhead is not
    a hard operating-system memory limit; process untrusted files in isolation.
    """
    width, height = _positive_int(width, "width"), _positive_int(height, "height")
    max_frames, max_pixels = _positive_int(max_frames, "max_frames"), _positive_int(max_pixels, "max_pixels")
    max_bytes = _positive_int(max_bytes, "max_bytes")
    if width * height > max_pixels:
        raise VideoLoadError("requested output dimensions exceed max_pixels")
    path = Path(path)
    if not path.exists():
        raise VideoLoadError(f"input does not exist: {path}")
    try:
        if path.is_dir():
            result = _png_directory(path, width, height, fps, max_frames, max_pixels, max_bytes)
            kind = "png_directory"
        elif path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            raise VideoLoadError("MP4/MOV/WebM decoding requires external ffmpeg, which this loader does not invoke. Convert the clip to a numbered PNG directory, preserving its source frame rate, then pass fps explicitly. Variable-rate video requires timestamp-aware conversion; do not silently assign constant fps.")
        elif fps is not None:
            raise VideoLoadError("fps is only accepted for PNG directories; timed NPZ/GIF inputs retain their source timing")
        elif path.suffix.lower() == ".npz":
            result = _npz(path, width, height, max_frames, max_pixels, max_bytes)
            kind = "npz"
        elif path.suffix.lower() == ".gif":
            result = _gif(path, width, height, max_frames, max_pixels, max_bytes)
            kind = "gif"
        else:
            raise VideoLoadError("supported inputs: .npz, animated .gif, or a PNG frame directory")
    except VideoLoadError:
        raise
    except (OSError, ValueError, EOFError, zipfile.BadZipFile, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise VideoLoadError(f"cannot decode input {path.name}: {exc}") from exc
    frames, durations, source_size, extra = result
    timestamps = []
    time = 0.0
    for duration in durations:
        timestamps.append(time)
        time += duration
    fixed_rate = all(math.isclose(d, durations[0], rel_tol=0, abs_tol=1e-12) for d in durations)
    return NormalizedVideo(
        frames=frames, fps=(1 / durations[0] if fixed_rate else None),
        original_indices=list(range(len(frames))), timestamps_seconds=timestamps,
        durations_seconds=durations,
        metadata={"source_kind": kind, "source_name": path.name, "source_size": source_size,
                  "output_size": [width, height], "frame_count": len(frames), "duration_seconds": time,
                  "variable_frame_rate": not fixed_rate, "temporal_resampling": False,
                  "truncated": False, "resize_filter": "Pillow BOX", **extra},
    )

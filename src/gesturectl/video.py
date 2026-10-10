"""Camera videos: recording, naming/labels, frame timestamps, and video -> landmarks.

Files live in ``videos/`` (gitignored: private and large). Naming convention, the
filename *is* the label:

    <gesture>_<anything>.mp4    one gesture, performed 5 times (``_x3`` = 3 times)
    none_<anything>.mp4         look-alike / random movements: nothing may fire
    drive_<anything>.mp4        real driving, no gestures: nothing may fire
    mixed_<anything>.mp4        normal movements with gestures thrown in; needs a
                                same-named .txt with ``m:ss gesture`` lines

The recorder writes a same-named ``.json`` sidecar with the real timestamp of every
frame, because gesture timing is in seconds and cameras do not deliver perfectly even
frame rates.

Turning video into landmarks (MediaPipe) is the slow part and does not depend on the
gesture thresholds, so results are cached in ``videos/.cache/``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from gesturectl.camera import prepare
from gesturectl.config import GESTURES, PROJECT_ROOT, AppConfig
from gesturectl.recording import Recording, load, save

VIDEOS_DIR = PROJECT_ROOT / "videos"
VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov")
DEFAULT_REPS = 5
SIDECAR_VERSION = 1
_NEGATIVE_LABELS = ("none", "drive")


# ------------------------------------------------------------------- naming / labels


@dataclass(frozen=True)
class VideoLabel:
    kind: str  # "gesture" | "negative" | "mixed"
    label: str  # gesture name, "none", "drive" or "mixed"
    reps: int = 0  # gesture clips only


def parse_video_name(stem: str) -> VideoLabel:
    """Label from a filename stem, e.g. ``swipe_left_driver_day_1`` or ``none_gearknob``."""
    for label in sorted(GESTURES + _NEGATIVE_LABELS + ("mixed",), key=len, reverse=True):
        if stem == label or stem.startswith(label + "_"):
            if label in GESTURES:
                m = re.search(r"(?:^|_)x(\d+)(?:_|$)", stem)
                return VideoLabel("gesture", label, int(m.group(1)) if m else DEFAULT_REPS)
            if label == "mixed":
                return VideoLabel("mixed", label)
            return VideoLabel("negative", label)
    known = ", ".join(GESTURES + _NEGATIVE_LABELS + ("mixed",))
    raise ValueError(f"{stem!r} does not start with a known label ({known})")


_TIME = re.compile(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$")


def read_labels(path: Path) -> list[tuple[float, str]]:
    """Read a mixed-take labels file: one ``m:ss gesture`` (or ``ss.s gesture``) per line,
    ``#`` starts a comment."""
    out = []
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        m = _TIME.match(parts[0]) if len(parts) == 2 else None
        if m is None:
            raise ValueError(f"{path}:{lineno}: expected '<m:ss> <gesture>', got {raw!r}")
        if parts[1] not in GESTURES:
            raise ValueError(f"{path}:{lineno}: unknown gesture {parts[1]!r}")
        out.append((int(m.group(1) or 0) * 60 + float(m.group(2)), parts[1]))
    return sorted(out)


def find_videos(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in VIDEO_EXTS and ".cache" not in f.parts]
        elif p.is_file():
            files.append(p)
    return files


# ------------------------------------------------------------------- recording


class VideoRecorder:
    """Writes camera frames to MP4 plus a timestamp sidecar. With ``split_s`` the take is
    cut into ``<stem>_part01.mp4``, ``_part02`` ... chunks of that many seconds."""

    def __init__(self, path: Path, fps: float, *, split_s: float | None = None, source: str = ""):
        self.path = Path(path)
        self.fps = fps
        self.split_s = split_s
        self.source = source
        self.written: list[Path] = []
        self._part = 0
        self._writer: cv2.VideoWriter | None = None
        self._chunk_path: Path | None = None
        self._times: list[float] = []
        self._chunk_start = 0.0
        self._size: tuple[int, int] | None = None

    def add(self, frame: np.ndarray, t: float) -> None:
        """Add one frame taken ``t`` seconds after the recording started."""
        if self._writer is not None and self.split_s and t - self._chunk_start >= self.split_s:
            self._close_chunk()
        if self._writer is None:
            self._open_chunk(frame, t)
        h, w = frame.shape[:2]
        if (w, h) != self._size:
            frame = cv2.resize(frame, self._size)
        self._writer.write(frame)
        self._times.append(t - self._chunk_start)

    def close(self) -> list[Path]:
        if self._writer is not None:
            self._close_chunk()
        return self.written

    def _open_chunk(self, frame: np.ndarray, t: float) -> None:
        if self.split_s:
            self._part += 1
            self._chunk_path = self.path.with_name(f"{self.path.stem}_part{self._part:02d}{self.path.suffix}")
        else:
            self._chunk_path = self.path
        self._chunk_path.parent.mkdir(parents=True, exist_ok=True)
        h, w = frame.shape[:2]
        self._size = (w, h)
        self._writer = cv2.VideoWriter(str(self._chunk_path), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, self._size)
        if not self._writer.isOpened():
            raise RuntimeError(f"could not open {self._chunk_path} for writing")
        self._times = []
        self._chunk_start = t

    def _close_chunk(self) -> None:
        self._writer.release()
        duration = self._times[-1] if self._times else 0.0
        meta = {
            "version": SIDECAR_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "source": self.source,
            "size": list(self._size),
            "nominal_fps": self.fps,
            "frames": len(self._times),
            "duration_s": round(duration, 3),
            "measured_fps": round((len(self._times) - 1) / duration, 2) if duration > 0 else 0.0,
            "frame_times": [round(t, 4) for t in self._times],
        }
        self._chunk_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        self.written.append(self._chunk_path)
        self._writer = None


# ------------------------------------------------------------------- reading


def read_sidecar(video: Path) -> dict | None:
    path = Path(video).with_suffix(".json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def iter_video(path: Path) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (seconds since start, BGR frame). Uses the sidecar timestamps when present,
    otherwise frame index / container fps."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {path}")
    meta = read_sidecar(path)
    times = meta.get("frame_times") if meta else None
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0 or fps > 240:
        fps = 30.0
    try:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield (float(times[i]) if times and i < len(times) else i / fps), frame
            i += 1
    finally:
        cap.release()


@dataclass
class TrackStats:
    frames_read: int
    frames_processed: int
    duration_s: float
    avg_inference_ms: float


def track_video(path: Path, cfg: AppConfig, fps: float | None = None) -> tuple[Recording, TrackStats]:
    """Run MediaPipe over a video, exactly like the live pipeline (same orientation and
    resize). ``fps`` processes only that many frames per second, simulating a slower
    device such as the Pi (MediaPipe's tracking sees the same gaps it would live)."""
    from gesturectl.tracker import HandTracker, largest  # imports mediapipe

    tracker = HandTracker(cfg.tracker, cfg.model_path())
    frames = []
    read = processed = 0
    infer_s = 0.0
    last_t = 0.0
    next_t: float | None = None
    try:
        for t, raw in iter_video(path):
            read += 1
            last_t = t
            if fps:
                if next_t is None:
                    next_t = t
                if t + 1e-6 < next_t:
                    continue
                next_t += 1.0 / fps
                if next_t <= t:  # after a gap in the video, don't try to catch up
                    next_t = t + 1.0 / fps
            frame = prepare(raw, cfg.camera)
            t0 = time.perf_counter()
            hand = largest(tracker.process(frame, t))
            infer_s += time.perf_counter() - t0
            processed += 1
            frames.append((t, hand))
    finally:
        tracker.close()

    label = parse_video_name(Path(path).stem)
    rec = Recording(
        label=label.label,
        frame_size=(cfg.camera.width, cfg.camera.height),
        frames=frames,
        note=Path(path).name,
        reps=label.reps or 1,
    )
    stats = TrackStats(read, processed, last_t, 1000.0 * infer_s / processed if processed else 0.0)
    return rec, stats


def _cache_key(path: Path, cfg: AppConfig, fps: float | None) -> str:
    st = path.stat()
    blob = json.dumps(
        {
            "v": 1,
            "video": [path.name, st.st_size, int(st.st_mtime)],
            "camera": asdict(cfg.camera),
            "tracker": asdict(cfg.tracker),
            "model_size": cfg.model_path().stat().st_size,
            "fps": fps,
        },
        sort_keys=True,
    )
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def landmarks_for(
    path: Path, cfg: AppConfig, fps: float | None = None, use_cache: bool = True
) -> tuple[Recording, TrackStats | None]:
    """Landmarks for a video, from ``videos/.cache`` when nothing relevant changed.
    Returns stats only when MediaPipe actually ran."""
    path = Path(path)
    cached = path.parent / ".cache" / f"{path.stem}.{_cache_key(path, cfg, fps)}.json"
    if use_cache and cached.exists():
        rec = load(cached)
        label = parse_video_name(path.stem)
        rec.label, rec.reps = label.label, label.reps or 1
        return rec, None
    rec, stats = track_video(path, cfg, fps)
    if use_cache:
        save(rec, cached, check_label=False)
    return rec, stats

"""Configuration: YAML file -> typed dataclasses, with strict validation.

Unknown keys are errors (a typo should fail loudly, not silently fall back to a default).
Relative paths (e.g. the model) are resolved against the project root, i.e. the folder
that contains ``config/``.
"""

from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"

GESTURES = (
    "circle_cw",
    "circle_ccw",
    "fist_to_open",
    "open_to_fist",
    "swipe_up",
    "swipe_down",
    "swipe_left",
    "swipe_right",
)
ACTIONS = (
    "volume_up",
    "volume_down",
    "play",
    "pause",
    "play_pause",
    "next",
    "previous",
    "answer_call",
    "end_call",
)
DEFAULT_MAPPING: dict[str, str | None] = {
    "circle_cw": "volume_up",
    "circle_ccw": "volume_down",
    "fist_to_open": "pause",
    "open_to_fist": "play",
    "swipe_down": "answer_call",
    "swipe_up": "end_call",
    "swipe_right": "next",
    "swipe_left": "previous",
}


class ConfigError(ValueError):
    pass


@dataclass
class CameraConfig:
    source: str = "opencv"  # "opencv" (USB / laptop webcam). "picamera2" arrives with the Pi stage.
    index: int = 0
    backend: str = "auto"  # auto | dshow | msmf | v4l2 | any
    width: int = 320  # processing size; frames are resized to this if the camera differs
    height: int = 240
    fps: int = 30
    flip_horizontal: bool = True  # mirror so the image matches the user's point of view
    rotate: int = 0  # 0 | 90 | 180 | 270, clockwise, applied after the flip


@dataclass
class TrackerConfig:
    model: str = "models/hand_landmarker.task"
    num_hands: int = 1
    min_detection: float = 0.6
    min_presence: float = 0.6
    min_tracking: float = 0.5


@dataclass
class GeometryConfig:
    # Finger straightness = |MCP->TIP| / (sum of the three segment lengths); 1.0 = straight.
    # Finger alignment = cos(angle between WRIST->MCP and MCP->TIP); 1.0 = pointing away from palm.
    extended_straightness: float = 0.80
    extended_alignment: float = 0.50
    curled_straightness: float = 0.55
    curled_alignment: float = 0.0
    thumb_open_distance: float = 0.45  # thumb tip to index MCP, in hand-scale units


@dataclass
class GatingConfig:
    active_zone: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)  # x0, y0, x1, y1 (0..1)
    min_hand_scale: float = 0.08  # hand scale as a fraction of frame height
    min_score: float = 0.5
    pose_switch_s: float = 0.1  # a new pose must persist this long to count
    dropout_grace_s: float = 0.2  # tolerated gap with no usable hand
    cooldown_s: float = 1.0  # after any gesture fires (continuous circles excepted)


@dataclass
class CircleConfig:
    min_step: float = 0.12  # fingertip path resampling distance (hand scales); filters jitter
    max_turn_deg: float = 135.0  # larger turns between segments are treated as noise
    first_step_deg: float = 360.0
    step_deg: float = 180.0
    reverse_reset_deg: float = 90.0
    min_diameter: float = 0.35  # hand scales
    idle_reset_s: float = 1.0
    first_step_max_s: float = 3.0


@dataclass
class GrabConfig:
    arm_hold_s: float = 0.4
    arm_max_drift: float = 0.3  # hand scales
    transition_max_s: float = 0.8
    transition_max_move: float = 0.5  # hand scales
    target_hold_s: float = 0.2


@dataclass
class SwipeConfig:
    arm_hold_s: float = 0.3
    arm_max_drift: float = 0.25  # hand scales
    start_distance: float = 0.25  # hand scales; movement beyond this starts the swipe clock
    min_distance: float = 1.0  # hand scales
    max_duration_s: float = 0.8
    axis_ratio: float = 2.0  # dominant axis must be this many times the other


@dataclass
class GesturesConfig:
    circle: CircleConfig = field(default_factory=CircleConfig)
    grab: GrabConfig = field(default_factory=GrabConfig)
    swipe: SwipeConfig = field(default_factory=SwipeConfig)


@dataclass
class OverlayConfig:
    scale: float = 2.0  # upscale factor for the debug window


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    gating: GatingConfig = field(default_factory=GatingConfig)
    gestures: GesturesConfig = field(default_factory=GesturesConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    mapping: dict[str, str | None] = field(default_factory=lambda: dict(DEFAULT_MAPPING))

    def model_path(self) -> Path:
        path = Path(self.tracker.model)
        return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load and validate a YAML config. ``None`` loads config/default.yaml."""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    cfg = from_dict(data)
    return cfg


def from_dict(data: dict[str, Any]) -> AppConfig:
    """Build an AppConfig from plain data (YAML-shaped). ``mapping`` replaces the default."""
    data = dict(data)
    mapping = data.pop("mapping", None)
    cfg = _build(AppConfig, data, "config")
    if mapping is not None:
        if not isinstance(mapping, dict):
            raise ConfigError("mapping: must be a mapping of gesture -> action")
        cfg.mapping = dict(mapping)
    validate(cfg)
    return cfg


def validate(cfg: AppConfig) -> None:
    for gesture, action in cfg.mapping.items():
        if gesture not in GESTURES:
            raise ConfigError(f"mapping: unknown gesture {gesture!r}; known: {', '.join(GESTURES)}")
        if action is not None and action not in ACTIONS:
            raise ConfigError(f"mapping.{gesture}: unknown action {action!r}; known: {', '.join(ACTIONS)}")

    cam = cfg.camera
    if cam.source not in ("opencv", "picamera2"):
        raise ConfigError(f"camera.source: expected 'opencv' or 'picamera2', got {cam.source!r}")
    if cam.backend not in ("auto", "dshow", "msmf", "v4l2", "any"):
        raise ConfigError(f"camera.backend: unknown backend {cam.backend!r}")
    if cam.rotate not in (0, 90, 180, 270):
        raise ConfigError(f"camera.rotate: must be 0, 90, 180 or 270, got {cam.rotate}")
    if cam.width <= 0 or cam.height <= 0 or cam.fps <= 0:
        raise ConfigError("camera.width/height/fps must be positive")

    if cfg.tracker.num_hands < 1:
        raise ConfigError("tracker.num_hands must be >= 1")

    x0, y0, x1, y1 = cfg.gating.active_zone
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ConfigError(f"gating.active_zone must be [x0, y0, x1, y1] within 0..1, got {cfg.gating.active_zone}")


def _build(cls: type, data: Any, where: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: expected a mapping, got {type(data).__name__}")
    hints = typing.get_type_hints(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data) - names
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {sorted(unknown)}; allowed: {sorted(names)}")
    kwargs = {}
    for name, value in data.items():
        kwargs[name] = _coerce(hints[name], value, f"{where}.{name}")
    return cls(**kwargs)


def _coerce(hint: Any, value: Any, where: str) -> Any:
    if dataclasses.is_dataclass(hint):
        return _build(hint, value, where)
    origin = typing.get_origin(hint)
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ConfigError(f"{where}: expected a list")
        args = typing.get_args(hint)
        if len(value) != len(args):
            raise ConfigError(f"{where}: expected {len(args)} values, got {len(value)}")
        return tuple(_coerce(a, v, where) for a, v in zip(args, value))
    if hint is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"{where}: expected true/false, got {value!r}")
        return value
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{where}: expected an integer, got {value!r}")
        return value
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{where}: expected a number, got {value!r}")
        return float(value)
    if hint is str:
        if not isinstance(value, str):
            raise ConfigError(f"{where}: expected a string, got {value!r}")
        return value
    return value

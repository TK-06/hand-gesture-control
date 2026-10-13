"""Configuration: YAML file -> typed dataclasses, with strict validation.

``config/default.yaml`` holds every setting. A per-machine file such as
``config/car.yaml`` is layered on top of it (``--config config/car.yaml``) and lists only
what differs, so thresholds tuned in default.yaml always reach the car.

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
    # static poses, held still
    "open_palm",
    "thumb_up",
    "thumb_right",
    "thumb_left",
    "thumb_down",
    "phone_vertical",
    "phone_horizontal",
    # older motion gestures (off by default)
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
    "open_palm": "pause",
    "thumb_up": "play",
    "thumb_right": "next",
    "thumb_left": "previous",
    "thumb_down": None,
    "phone_vertical": "answer_call",
    "phone_horizontal": "end_call",
    "fist_to_open": None,
    "open_to_fist": None,
    "swipe_up": None,
    "swipe_down": None,
    "swipe_left": None,
    "swipe_right": None,
}


class ConfigError(ValueError):
    pass


@dataclass
class CameraConfig:
    source: str = "auto"  # auto (Pi ribbon camera if found, else OpenCV) | opencv | picamera2
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
    # A straight index finger counts as pointing even when bent at the knuckle, i.e.
    # pointing toward the camera (the natural way to draw volume circles).
    point_straightness: float = 0.88
    point_min_alignment: float = -0.6


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
    first_step_deg: float = 270.0  # first volume step after 3/4 of a circle
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
class StaticConfig:
    hold_s: float = 0.6  # hold the pose this long to fire
    max_drift: float = 0.3  # hand scales; moving more than this restarts the hold
    release_s: float = 0.3  # show something else this long before the same pose fires again
    thumb_tolerance_deg: float = 35.0  # how far off up/right/left/down the thumb may point
    phone_tolerance_deg: float = 30.0  # how far off vertical/horizontal the phone hand may be
    repeat_s: float = 2.0  # keep holding a repeating pose: fire again every repeat_s (0 = off)
    repeat_gestures: list[str] = field(default_factory=lambda: ["thumb_right", "thumb_left"])


@dataclass
class GesturesConfig:
    circle: CircleConfig = field(default_factory=CircleConfig)
    static: StaticConfig = field(default_factory=StaticConfig)
    grab: GrabConfig = field(default_factory=GrabConfig)
    swipe: SwipeConfig = field(default_factory=SwipeConfig)


@dataclass
class OverlayConfig:
    scale: float = 2.0  # upscale factor for the debug window


@dataclass
class ActionsConfig:
    backend: str = "print"  # print (log only) | bt_hid (send to the Bluetooth remote service)


@dataclass
class HidConfig:
    """The Bluetooth LE remote service (python -m gesturectl.hid)."""

    name: str = "Gesture Remote"  # shown in the iPhone's Bluetooth list
    adapter: str = "hci0"
    profile: str = "media"  # media | media+keyboard (fallback if iOS ignores a media-only remote)
    host: str = "127.0.0.1"  # where the service listens for actions (local only)
    port: int = 47231
    pairing_window_s: float = 120.0  # how long `pair` accepts a new phone
    key_press_s: float = 0.15  # key down -> key up; iOS ignores volume taps much shorter than this


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    gating: GatingConfig = field(default_factory=GatingConfig)
    gestures: GesturesConfig = field(default_factory=GesturesConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)
    hid: HidConfig = field(default_factory=HidConfig)
    mapping: dict[str, str | None] = field(default_factory=lambda: dict(DEFAULT_MAPPING))

    def model_path(self) -> Path:
        path = Path(self.tracker.model)
        return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load and validate the config. ``config/default.yaml`` is always the base; ``path``
    (e.g. ``config/car.yaml``) is layered on top and only needs the values that differ.
    Sections merge key by key; a ``mapping:`` in the override replaces the whole mapping."""
    data = _read_yaml(DEFAULT_CONFIG)
    if path is not None and Path(path).resolve() != Path(DEFAULT_CONFIG).resolve():
        data = _merge(data, _read_yaml(Path(path)))
    return from_dict(data)


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key != "mapping" and isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


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
    if cam.source not in ("auto", "opencv", "picamera2"):
        raise ConfigError(f"camera.source: expected 'auto', 'opencv' or 'picamera2', got {cam.source!r}")
    if cam.backend not in ("auto", "dshow", "msmf", "v4l2", "any"):
        raise ConfigError(f"camera.backend: unknown backend {cam.backend!r}")
    if cam.rotate not in (0, 90, 180, 270):
        raise ConfigError(f"camera.rotate: must be 0, 90, 180 or 270, got {cam.rotate}")
    if cam.width <= 0 or cam.height <= 0 or cam.fps <= 0:
        raise ConfigError("camera.width/height/fps must be positive")

    if cfg.actions.backend not in ("print", "bt_hid"):
        raise ConfigError(f"actions.backend: expected 'print' or 'bt_hid', got {cfg.actions.backend!r}")
    if cfg.hid.profile not in ("media", "media+keyboard"):
        raise ConfigError(f"hid.profile: expected 'media' or 'media+keyboard', got {cfg.hid.profile!r}")
    if not 1 <= cfg.hid.port <= 65535:
        raise ConfigError(f"hid.port: must be 1..65535, got {cfg.hid.port}")

    for gesture in cfg.gestures.static.repeat_gestures:
        if gesture not in GESTURES:
            raise ConfigError(f"gestures.static.repeat_gestures: unknown gesture {gesture!r}")

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
    if origin is list:
        if not isinstance(value, list):
            raise ConfigError(f"{where}: expected a list")
        (item,) = typing.get_args(hint)
        return [_coerce(item, v, f"{where}[{i}]") for i, v in enumerate(value)]
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

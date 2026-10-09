"""Gesture engine: gating -> pose -> recognizers -> cooldown -> gesture-to-action mapping."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from gesturectl.config import AppConfig
from gesturectl.geometry import Pose, classify_pose, hand_scale, palm_center
from gesturectl.gestures import CircleRecognizer, GrabRecognizer, Observation, Recognizer, SwipeRecognizer
from gesturectl.hand import HandFrame
from gesturectl.pose_filter import PoseFilter

log = logging.getLogger(__name__)

# Gestures that may fire repeatedly inside the cooldown, as one continuous motion.
REPEATABLE = frozenset({"circle_cw", "circle_ccw"})


@dataclass(frozen=True)
class Event:
    t: float
    gesture: str
    action: str


class GestureEngine:
    def __init__(self, cfg: AppConfig, recognizers: list[Recognizer] | None = None):
        self.cfg = cfg
        self.pose_filter = PoseFilter(cfg.gating.pose_switch_s, cfg.gating.dropout_grace_s)
        self.recognizers = recognizers or [
            CircleRecognizer(cfg.gestures.circle),
            GrabRecognizer(cfg.gestures.grab),
            SwipeRecognizer(cfg.gestures.swipe),
        ]
        self._cooldown_until = -math.inf
        self._last_gesture: str | None = None
        # For the overlay / debugging.
        self.raw_pose = Pose.NONE
        self.gate_reason = "no hand"
        self.last_obs: Observation | None = None

    def update(self, t: float, hand: HandFrame | None) -> list[Event]:
        usable, self.gate_reason = self._gate(hand)
        if usable is not None:
            self.raw_pose = classify_pose(usable.landmarks, self.cfg.geometry)
            scale = hand_scale(usable.landmarks)
            palm = palm_center(usable.landmarks)
        else:
            self.raw_pose, scale, palm = Pose.NONE, 0.0, None
        pose, since = self.pose_filter.update(t, self.raw_pose)
        obs = Observation(t=t, hand=usable, pose=pose, pose_since=since, scale=scale, palm=palm)
        self.last_obs = obs

        events: list[Event] = []
        for recognizer in self.recognizers:
            for gesture in recognizer.update(obs):
                event = self._admit(t, gesture)
                if event is not None:
                    events.append(event)
        return events

    def cooldown_remaining(self, t: float) -> float:
        return max(0.0, self._cooldown_until - t)

    def status_lines(self) -> list[str]:
        return [r.status() for r in self.recognizers]

    def _admit(self, t: float, gesture: str) -> Event | None:
        action = self.cfg.mapping.get(gesture)
        if action is None:
            log.debug("gesture %s is not mapped; ignored", gesture)
            return None
        in_cooldown = t < self._cooldown_until
        if in_cooldown and not (gesture == self._last_gesture and gesture in REPEATABLE):
            log.info("gesture %s suppressed (cooldown %.2fs left)", gesture, self._cooldown_until - t)
            return None
        self._cooldown_until = t + self.cfg.gating.cooldown_s
        self._last_gesture = gesture
        return Event(t=t, gesture=gesture, action=action)

    def _gate(self, hand: HandFrame | None) -> tuple[HandFrame | None, str]:
        if hand is None:
            return None, "no hand"
        g = self.cfg.gating
        if hand.score < g.min_score:
            return None, f"low score {hand.score:.2f}"
        width, height = hand.frame_size
        if hand_scale(hand.landmarks) < g.min_hand_scale * height:
            return None, "hand too small / far"
        x, y = palm_center(hand.landmarks)
        x0, y0, x1, y1 = g.active_zone
        if not (x0 * width <= x <= x1 * width and y0 * height <= y <= y1 * height):
            return None, "outside active zone"
        return hand, "ok"

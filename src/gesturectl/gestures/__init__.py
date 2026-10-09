"""Dynamic gesture recognizers. Each consumes Observations and returns fired gesture names."""

from gesturectl.gestures.base import Observation, Recognizer
from gesturectl.gestures.circle import CircleRecognizer
from gesturectl.gestures.grab import GrabRecognizer
from gesturectl.gestures.swipe import SwipeRecognizer

__all__ = ["Observation", "Recognizer", "CircleRecognizer", "GrabRecognizer", "SwipeRecognizer"]

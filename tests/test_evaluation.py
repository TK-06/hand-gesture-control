from collections import Counter

from gesturectl.engine import Event
from gesturectl.evaluation import collapse, fmt_time, score_gesture_clip, score_mixed, score_negative


def ev(*spec):
    return [Event(t=float(t), gesture=g, action="x") for t, g in spec]


def test_collapse_merges_steps_of_one_circle_but_not_one_shot_gestures():
    events = ev(
        (1.0, "circle_cw"), (1.5, "circle_cw"), (2.0, "circle_cw"),  # one continuous circle
        (5.0, "circle_cw"),  # a second circle
        (6.0, "swipe_left"), (6.5, "swipe_left"),
    )
    assert collapse(events) == [(1.0, "circle_cw"), (5.0, "circle_cw"), (6.0, "swipe_left"), (6.5, "swipe_left")]


def test_gesture_clip_all_detected():
    s = score_gesture_clip("swipe_left", 5, ev(*[(t, "swipe_left") for t in (2, 5, 8, 11, 14)]))
    assert s.hit["swipe_left"] == 5 and not s.missed and not s.false


def test_gesture_clip_with_misses_and_a_confusion():
    s = score_gesture_clip("swipe_left", 5, ev((2, "swipe_left"), (5, "swipe_right"), (8, "swipe_left")))
    assert s.hit["swipe_left"] == 2
    assert len(s.missed) == 3
    assert s.false == [(5.0, "swipe_right")]


def test_gesture_clip_extra_detections_count_as_false():
    s = score_gesture_clip("open_to_fist", 1, ev((2, "open_to_fist"), (4, "open_to_fist")))
    assert s.hit["open_to_fist"] == 1 and s.false == [(4.0, "open_to_fist")]


def test_circle_clip_counts_circles_not_volume_steps():
    events = ev(*[(t, "circle_cw") for t in (1, 1.5, 2, 6, 6.5, 10)])
    s = score_gesture_clip("circle_cw", 3, events)
    assert s.hit["circle_cw"] == 3 and not s.false


def test_negative_footage():
    s = score_negative(ev((10, "fist_to_open")), 600.0)
    assert s.false == [(10.0, "fist_to_open")] and s.negative_s == 600.0


def test_mixed_take_matches_within_tolerance():
    expected = [(12.0, "swipe_right"), (40.0, "circle_cw"), (65.0, "fist_to_open")]
    events = ev((13.1, "swipe_right"), (41.0, "circle_cw"), (41.5, "circle_cw"), (90.0, "swipe_up"))
    s = score_mixed(expected, events, tolerance_s=2.5)
    assert s.hit == Counter({"swipe_right": 1, "circle_cw": 1})
    assert s.missed == [(65.0, "fist_to_open")]
    assert s.false == [(90.0, "swipe_up")]


def test_mixed_take_wrong_gesture_at_the_right_time_is_a_miss_and_a_false():
    s = score_mixed([(10.0, "swipe_left")], ev((10.2, "swipe_right")))
    assert s.missed == [(10.0, "swipe_left")] and s.false == [(10.2, "swipe_right")]


def test_mixed_take_detection_too_late_does_not_count():
    s = score_mixed([(10.0, "swipe_left")], ev((14.0, "swipe_left")), tolerance_s=2.5)
    assert s.missed == [(10.0, "swipe_left")] and s.false == [(14.0, "swipe_left")]


def test_fmt_time():
    assert fmt_time(65.3) == "1:05.3"
    assert fmt_time(None) == "?"

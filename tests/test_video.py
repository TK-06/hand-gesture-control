import json

import numpy as np
import pytest

from gesturectl.config import AppConfig
from gesturectl.video import (
    VideoLabel,
    VideoRecorder,
    find_videos,
    iter_video,
    landmarks_for,
    parse_video_name,
    read_labels,
)


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("swipe_left_driver_day_1", VideoLabel("gesture", "swipe_left", 5)),
        ("swipe_left", VideoLabel("gesture", "swipe_left", 5)),
        ("circle_ccw_x3_passenger_night", VideoLabel("gesture", "circle_ccw", 3)),
        ("open_to_fist_driver_x7", VideoLabel("gesture", "open_to_fist", 7)),
        ("none_gearknob_1", VideoLabel("negative", "none")),
        ("drive_day_1_part02", VideoLabel("negative", "drive")),
        ("mixed_driver_day_1", VideoLabel("mixed", "mixed")),
    ],
)
def test_parse_video_name(stem, expected):
    assert parse_video_name(stem) == expected


@pytest.mark.parametrize("stem", ["wave_1", "swipe", "noneish", "driver_day"])
def test_unknown_video_names_are_rejected(stem):
    with pytest.raises(ValueError):
        parse_video_name(stem)


def test_read_labels(tmp_path):
    path = tmp_path / "mixed.txt"
    path.write_text("# my take\n0:12 swipe_right\n\n1:05.5 fist_to_open  # a bit late\n40 circle_cw\n", encoding="utf-8")
    assert read_labels(path) == [(12.0, "swipe_right"), (40.0, "circle_cw"), (65.5, "fist_to_open")]


@pytest.mark.parametrize("line", ["0:12", "abc swipe_left", "0:12 wave"])
def test_bad_label_lines_are_errors(tmp_path, line):
    path = tmp_path / "mixed.txt"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_labels(path)


def _frames(n, w=64, h=48):
    rng = np.random.default_rng(0)
    return [rng.integers(0, 255, (h, w, 3), dtype=np.uint8) for _ in range(n)]


def test_recorder_keeps_real_frame_timestamps(tmp_path):
    times = [0.0, 0.11, 0.19, 0.33, 0.41]  # uneven, like a real camera
    rec = VideoRecorder(tmp_path / "none_test.mp4", fps=10)
    for frame, t in zip(_frames(5), times):
        rec.add(frame, t)
    written = rec.close()

    assert written == [tmp_path / "none_test.mp4"]
    assert [t for t, _ in iter_video(written[0])] == pytest.approx(times)
    meta = json.loads((tmp_path / "none_test.json").read_text(encoding="utf-8"))
    assert meta["frames"] == 5 and meta["size"] == [64, 48]


def test_video_without_sidecar_uses_container_fps(tmp_path):
    rec = VideoRecorder(tmp_path / "none_test.mp4", fps=10)
    for i, frame in enumerate(_frames(4)):
        rec.add(frame, i * 0.1)
    path = rec.close()[0]
    path.with_suffix(".json").unlink()
    assert [t for t, _ in iter_video(path)] == pytest.approx([0.0, 0.1, 0.2, 0.3])


def test_recorder_splits_long_takes_into_parts(tmp_path):
    rec = VideoRecorder(tmp_path / "drive_day.mp4", fps=10, split_s=1.0)
    for i, frame in enumerate(_frames(25)):
        rec.add(frame, i * 0.1)
    written = rec.close()
    assert [p.name for p in written] == ["drive_day_part01.mp4", "drive_day_part02.mp4", "drive_day_part03.mp4"]
    second = [t for t, _ in iter_video(written[1])]
    assert len(second) == 10 and second[0] == 0.0  # each part starts at 0


def test_find_videos_skips_sidecars_and_cache(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "b.mp4").write_bytes(b"")
    assert find_videos([tmp_path]) == [tmp_path / "a.mp4"]


@pytest.mark.skipif(not AppConfig().model_path().exists(), reason="model not downloaded")
def test_landmarks_for_simulates_a_slower_device_and_caches(tmp_path):
    path = tmp_path / "none_blank.mp4"
    rec = VideoRecorder(path, fps=30)
    for i in range(30):
        rec.add(np.zeros((240, 320, 3), np.uint8), i / 30)
    rec.close()
    cfg = AppConfig()

    first, stats = landmarks_for(path, cfg, fps=10)
    assert stats.frames_read == 30 and stats.frames_processed == 10
    assert all(hand is None for _, hand in first.frames)

    second, stats = landmarks_for(path, cfg, fps=10)
    assert stats is None  # served from videos/.cache
    assert len(second.frames) == 10 and second.label == "none"
    assert len(list((tmp_path / ".cache").glob("*.json"))) == 1

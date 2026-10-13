# handGestureControl

Control your car's music with hand gestures, BMW-style. A small camera watches your hand.
Recognized gestures become media keys (volume, play, pause, next, previous) sent over
Bluetooth to your phone, which keeps playing through the car stereo as usual.

Target hardware is a headless Raspberry Pi 4 (2 GB) that pairs with the phone as a
**Bluetooth HID media remote**. It deliberately does not act as an audio sink, so phone
audio is never pulled away from the car. Development and testing happen on a normal
laptop with a webcam.

> **Status:** Stages 1–2 are done: vision and gesture recognition, running on a laptop.
> Gestures are detected and printed; sending them to a phone (Bluetooth) is the next
> milestone. See the [Roadmap](#roadmap).

> **Safety:** a hobby project, not a certified automotive product. It is meant to
> *reduce* reaching for the phone while driving. Keep your eyes on the road and use it at
> your own risk.

## How it works

```
camera ──► MediaPipe Hand Landmarker ──► 21 hand landmarks ──► pose + motion rules ──► gesture ──► action
 (320x240)  (detect once, then track)                          (finger states, held          (YAML mapping)
                                                                poses, circles)
```

- **Model.** [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
  (Tasks API) in VIDEO mode. Its palm detector only runs again when tracking is lost,
  which keeps it light enough for a Raspberry Pi 4.
- **No training.** Gestures are recognized with plain geometry on the landmarks. No
  model training is needed; thresholds are tuned with your own recorded samples.
- **Either hand.** Every rule is independent of left/right hand, rotation and distance,
  so the driver and the passenger can both use it.

## Gestures

Most gestures are **poses you hold still for about half a second**. At the Pi 4's ~9
frames per second, held poses are far more reliable than fast motions. The hold also
means ordinary hand movements (steering, gear changes, scratching your face) don't
fire anything. Directions are as **you** see them, and everything works with either
hand (driver's left, passenger's right).

| Gesture | How to do it | Action (default) |
|---|---|---|
| `open_palm` | **Five fingers up**, held still | `pause` |
| `thumb_up` | **Thumbs up**, held still | `play` |
| `thumb_right` / `thumb_left` | Fist with the **thumb pointing to your right / left** | `next` / `previous` |
| `phone_vertical` | **"Phone" hand** (thumb + pinky out), held **upright** like a phone | `answer_call` |
| `phone_horizontal` | Same hand held **sideways** (either way round) | `end_call` |
| `circle_cw` / `circle_ccw` | **Index finger only**, draw circles clockwise / counter-clockwise | `volume_up` / `volume_down` |

How they work:

- **Held poses** fire once after about 0.6 s held still. Moving the hand restarts the
  hold, so a hand passing through a pose never fires. To do the same one again, lower
  your hand (or show something else) first.
- **Circles:** the first volume step needs one full circle; after that, every half
  circle adds another step while you keep going. Reversing direction restarts the count.
- **Cooldown:** 1 s after any gesture, other gestures are ignored. Continuous circling is
  the exception.
- **Remapping:** change the `mapping:` section in `config/default.yaml`. Map a gesture to
  `null` to disable it. `thumb_down` is available but unused.
- **Older motion gestures** (two-finger swipes, fist ↔ open) are still in the code but
  switched off: they were unreliable at the Pi's frame rate. Map them in the config to
  turn them back on.

## Quickstart (laptop with a webcam)

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
python scripts/download_model.py  # fetches models/hand_landmarker.task (7.8 MB)
python -m gesturectl              # debug window; press Q to quit
```

The debug window shows:

- landmarks;
- the current pose, with the raw per-frame pose in brackets;
- why a hand is being ignored, if it is (too small, outside the zone, low confidence);
- each recognizer's state, the cooldown, FPS and inference time;
- a banner for every fired action.

Fired actions are also printed as `ACTION volume_up (gesture circle_cw)`.

Useful options:

- `--no-window` runs headless and logs FPS every 5 s.
- `--duration 30` stops after 30 seconds.
- `--config other.yaml` uses a different config file.
- `--log-level DEBUG` logs more detail.

If the wrong camera opens (many laptops also have an IR camera for face login), change
`camera.index` in `config/default.yaml`.

## Tune it to your hand: record, replay, test

1. **Record** takes of each gesture. Use both hands and different distances, and do 5 or
   more per gesture. Only landmark coordinates are saved, never images.

   ```bash
   python scripts/record_samples.py --label circle_cw
   ```

   SPACE starts a take, SPACE again stops and saves it to `samples/<label>/`. Q quits.
   Each saved take is replayed straight away and marked PASS or FAIL.

2. **Record "none" takes**: normal movements that must fire nothing. Reach for things,
   grip and release the gear knob, mime steering, scratch your face, wave.

   ```bash
   python scripts/record_samples.py --label none --note "gear knob"
   ```

3. **Replay** all samples against the current config. Edit thresholds in the YAML and
   replay again until everything passes.

   ```bash
   python scripts/replay_samples.py
   ```

4. **Test.** `pytest` runs the synthetic-hand tests plus every recorded sample in
   `samples/`.

All thresholds live in `config/default.yaml`, with comments. Distances are in "hand
scales" (wrist to middle knuckle), so they work at any distance from the camera.

## Test with the real camera: videos

With the Pi and camera mounted in the car, record short videos and score them on the
laptop. The filename is the label, e.g. `thumb_left_driver_day_1.mp4` or
`none_gearknob_1.mp4`.

```bash
python scripts/record_video.py videos/thumb_left_driver_day_1.mp4 --duration 45   # on the Pi
python scripts/evaluate_videos.py --config config/car.yaml --fps 12              # hit rate + false triggers
```

- `--fps` simulates the Pi's processing rate.
- Hand tracking is cached, so re-scoring after a threshold change takes seconds.
- `--export-samples` turns clips that behave correctly into regression tests in
  `samples/`.
- Videos stay in `videos/`, which is gitignored.

Guides:

- [docs/SETUP.md](docs/SETUP.md): Raspberry Pi setup, from flashing the card to the
  first run.
- [docs/RECORDING.md](docs/RECORDING.md): the shot list.

## Roadmap

| Stage | What | Status |
|---|---|---|
| 1 | Vision: camera, hand landmarks, debug overlay | ✅ done (laptop); Pi camera support written, untested on hardware |
| 2 | Gesture recognition, safety gating, YAML mapping, sample recording | ✅ done (laptop) |
| 2b | Real-camera video recording + scoring, tuning on in-car footage | tools done; recording in progress |
| 3 | Action layer with pluggable backends (`print`, `bt_hid`) | next |
| 4 | Bluetooth HID consumer-control device on the Pi (BlueZ): pairing, auto-reconnect | next |
| 5 | Answering calls: investigation only (HID has no "answer" key) | later |
| 6 | Deployment: systemd service, rotating logs, install script | later |

## Project layout

```
config/default.yaml     all settings + gesture -> action mapping
docs/                   SETUP.md (Raspberry Pi), RECORDING.md (shot list)
scripts/                download_model.py, record_samples.py, replay_samples.py,
                        record_video.py, evaluate_videos.py
src/gesturectl/
  camera.py             OpenCV or Pi ribbon camera (picamera2), flip/rotate, fit to 320x240
  tracker.py            MediaPipe Hand Landmarker (VIDEO mode: detect, then track)
  geometry.py           finger states and poses (open, fist, point, two)
  pose_filter.py        debounce poses, bridge short tracking dropouts
  gestures/             static.py (held poses), circle.py; grab.py, swipe.py (off by default)
  engine.py             gating (zone, size, confidence), cooldown, mapping
  overlay.py            debug window
  recording.py          sample file format + replay
  video.py              video recording, labels from filenames, video -> landmarks (cached)
  evaluation.py         scoring detections against what was performed
tests/                  synthetic-hand tests (synth.py) + recorded-sample tests
samples/                recorded landmark samples (test data)
videos/                 camera recordings (gitignored, private)
```

## Hardware shopping list (Pi stage; planned, not yet tested)

| Part | Notes |
|---|---|
| Raspberry Pi 4 Model B, 2 GB | Raspberry Pi OS **(Legacy, 64-bit) Lite** = Bookworm, headless. Not Trixie: see the MediaPipe note under Known limitations. |
| Case with heatsink and fan | Inference keeps the CPU busy, and cars get hot. The Pi 4 is rated for 0–50 °C ambient; a parked car in the sun is hotter than that. |
| microSD, 32 GB, "high endurance" | Survives sudden power cuts better. |
| Camera, either: | |
| · Pi Camera Module (OV5647, 15-pin CSI) | Plugs straight into the Pi 4. Buy a longer ribbon (30–50 cm) for mounting. |
| · or a UVC USB webcam | Simplest; works exactly like a laptop webcam. |
| Car USB charger, 5 V / 3 A USB-C port, plus a good cable | A weak supply causes under-voltage throttling and crashes. |
| Optional: NoIR camera + 850 nm IR illuminator | For night driving. **Unproven:** MediaPipe hand tracking is reported to work poorly on IR images. Test before relying on it. |

## Mounting notes (planned)

- **Placement.** Point the camera at a gesture zone in front of the centre stack, for
  example from the roof console looking down (as BMW does) or from the dash looking up.
  - Keep the gear lever out of view, or exclude it with `gating.active_zone`.
  - Gripping and releasing the gear knob looks a lot like the fist ↔ open gestures.
- **Glare and view.** Avoid aiming at windows: sun glare, plus hands outside the car.
- **Orientation.** Set `camera.flip_horizontal` and `camera.rotate` so the debug image
  matches what you see. Put car-specific settings in `config/car.yaml`, which is layered
  on top of `default.yaml`; it currently holds `rotate: 180` for an upside-down mount.
  Run with `--config config/car.yaml`.
  - A camera facing you (laptop, or dash looking at you) needs `flip_horizontal: true`.
  - A roof camera looking down usually needs `false` plus a `rotate` value. With a roof
    camera, "up" in the image means toward the windscreen, so "thumb up" and "phone
    upright" mean pointing forward.
- **CSI ribbon (Pi 4).** The contacts face the HDMI ports; the blue tab faces the USB
  and Ethernet ports.
- **Cables.** Route them away from airbag zones and pedals.
- **Power cuts.** Car USB power cuts out with the ignition, which can corrupt the SD
  card. Stage 6 will cover this (e.g. a read-only root filesystem).

## Known limitations / not yet verified

- **Pi 4 performance.** Reported at about 14 FPS for one hand with older MediaPipe;
  not measured with this code. All gesture timing is in seconds, not frames, so it
  should behave the same at about 10 FPS. Tests replay gestures at both 10 and 30 FPS.
- **mediapipe on the Pi 4.** MediaPipe 1.x for ARM needs AES CPU instructions the Pi 4
  lacks, so it crashes there. The Pi uses **mediapipe 0.10.18 on Raspberry Pi OS
  Bookworm (Python 3.11)**; `requirements.txt` selects it automatically on ARM Linux.
  The laptop keeps 1.0.1. Both versions give identical landmarks on a test photo, and
  the full test suite passes on both. See [docs/SETUP.md](docs/SETUP.md).
- **Pi ribbon camera.** `camera.source: picamera2` (picked automatically by `auto`) is
  written and tested against a stand-in, but has not run on a real Pi yet.
- **Night driving.** A normal RGB camera can't see a hand in a dark cabin; see the IR
  note above.
- **Calls.** Bluetooth HID has no "answer call" key. The call gestures are recognized, but
  may never reach the phone (Stage 5 investigation).
- **iPhone and play/pause.** iOS may only honour the HID Play/Pause *toggle*. If the
  separate `play` and `pause` keys are ignored, map both grabs to `play_pause`.
- **Open palm direction.** "Five fingers up" checks finger extension only, not which
  way the palm faces.

## License

[MIT](LICENSE) © 2026 Taj Kongsaeree.

The hand-tracking model (`hand_landmarker.task`) is not included in this repository.
`scripts/download_model.py` fetches it from Google; it is part of
[MediaPipe](https://github.com/google-ai-edge/mediapipe), licensed under Apache 2.0.

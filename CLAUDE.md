# handGestureControl: notes for Claude

A car hand-gesture media controller. A camera watches a hand, gestures become media
commands, and a Raspberry Pi sends them to the phone over Bluetooth. User-facing docs,
the hardware list and mounting notes are in `README.md`; read it first.

## Locked decisions (ask before changing)

- **Bluetooth HID only.** The Pi is a Bluetooth **HID consumer-control device**
  (media keys) paired to the phone. It is NOT an A2DP sink, because that would pull
  phone audio away from the car stereo.
- **Phone:** iPhone.
- **Target hardware:** Raspberry Pi 4 **2 GB**, Raspberry Pi OS Lite 64-bit, headless
  (SSH only). Camera: CSI (OV5647) or USB webcam, chosen via config. Powered from a car
  USB charger.
- **Portability:** the same code runs on the laptop and the Pi; board and camera
  differences live in `config/default.yaml`.
- **Model:** MediaPipe Hand Landmarker (Tasks API, `mediapipe==1.0.1`) in VIDEO mode,
  one hand, 320x240. Gestures are **rule-based geometry, not a trained model**: no
  training data or videos are needed.
- **Gesture design** (user's, BMW-inspired; works with either hand):
  - Index finger only, circling clockwise / counter-clockwise: volume up / down.
    The first step needs 360°, then one step per 180°.
  - Fist → five fingers up: `pause`. Five fingers up → fist: `play`.
    (These are separate actions, not a toggle.)
  - Index + middle (V) swipe: right `next`, left `previous`, down `answer_call`,
    up `end_call`.
- **Safety beats speed.** Every gesture has a still arm pose. Grab transitions must
  happen in place. Grab and swipe latch until the pose is released. A 1 s global
  cooldown applies (repeated circling is exempt). Hands that are too small, outside the
  active zone, or low-confidence are ignored.

## Status (2026-10-02)

| Stage | Status |
|---|---|
| 1 Vision (camera, landmarks, debug overlay) | Done, verified on laptop (~20 FPS, ~10–14 ms inference) |
| 2 Gestures, gating, YAML mapping, sample record/replay | Done; tested on synthetic hands only |
| 3 Action layer: `send(action)` with `print` and `bt_hid` backends | **Next** |
| 4 BlueZ HID on the Pi, pairing, auto-reconnect, `docs/SETUP.md` | Needs the Pi |
| 5 Answering calls | **Investigate and report only**; HID has no answer key |
| 6 systemd service, rotating log, install script | Needs the Pi |

Waiting on the user:

- Live test results, plus recorded samples (`samples/`) and `replay_samples.py` output,
  used to tune thresholds.
- Which add-on to build next (offered, not yet answered):
  - **A:** run the pipeline on a video file (phone footage from the car mount spot).
  - **B:** Stage 3 with a laptop media-keys backend (control Spotify on the laptop).
  - **C:** a Pi-speed throttle (~10 FPS).
- Camera type and mount location (roof vs dash). These set flip/rotate and the active
  zone.
- iPhone model and iOS version, for Stage 4.

## Commands

```bash
# Windows: .venv\Scripts\activate   (venv is Python 3.13; code must stay 3.11-compatible)
pip install -r requirements-dev.txt && pip install -e .
python scripts/download_model.py          # models/hand_landmarker.task (gitignored)
python -m gesturectl                      # debug window, Q quits
python -m gesturectl --no-window --duration 10   # headless smoke run, logs FPS
pytest -q                                 # synthetic tests + every file in samples/
python scripts/record_samples.py --label <gesture|none>
python scripts/replay_samples.py          # PASS/FAIL per recorded sample
```

## Code map and conventions

- **Pipeline:**
  `camera.py` (OpenCV, flip/rotate, centre-crop to 320x240)
  → `tracker.py` (MediaPipe → `HandFrame` in pixel units)
  → `engine.py` (gating → `geometry.classify_pose` → `PoseFilter` → recognizers in
  `gestures/` → cooldown → `mapping`)
  → `Event(gesture, action)`.
- `app.Pipeline` is shared by `__main__` and the recorder.
- **Units.** Thresholds are in **hand scales** (wrist → middle MCP) and **seconds**,
  never frames or pixels, so behaviour is the same at 10 FPS on the Pi and 30 FPS on
  the laptop.
- **Coordinates.** Image y points down, so a positive turn angle is clockwise on screen.
  `flip_horizontal: true` makes the image match the user's view on a facing camera.
- **Config.** Every tunable lives in `config/default.yaml` and mirrors the dataclass
  defaults in `config.py`; `test_default_yaml_matches_code_defaults` enforces this.
  Unknown keys are errors. `mapping:` replaces the default mapping entirely.
- **Tests come first.** `tests/synth.py` builds 3D synthetic hands (any pose, size,
  rotation, left or right) and trajectories. Cover positive cases at 10 and 30 FPS with
  both hands, **plus negatives** (accidental-trigger cases).
- **Samples.** `samples/<label>/*.json` hold landmarks only (no images). They are
  regression test data and get committed. The `none` label means "must fire nothing".
- **Dependencies** are pinned in `requirements.txt`. Each pin needs Windows x64 and
  Linux aarch64 wheels, for Python 3.11–3.13. That's why numpy is held at 2.4.x (2.5
  needs Python 3.12+). Use `opencv-contrib-python` (mediapipe depends on it); never also
  install `opencv-python`.

## Gotchas

- **mediapipe 1.0** is a ctypes wrapper; `mp.solutions` is gone.
  - Import with `from mediapipe.tasks.python import vision` and
    `from mediapipe.tasks.python.core.base_options import BaseOptions`.
  - `import mediapipe.tasks.python as tasks` fails.
- **Heavy imports.** Importing mediapipe also loads `sounddevice` and `matplotlib`.
  The Pi will likely need `sudo apt install libportaudio2`. This is unverified.
- **Laptop cameras.** The laptop webcam delivers 640x360 natively, which is
  centre-cropped to 4:3. The laptop also has an IR camera, so check `camera.index`.
- **Not implemented yet:** `camera.source: picamera2` (Pi CSI). It raises
  `NotImplementedError` until the Pi stage.

## Unverified / risks to keep flagging

- Pi 4 FPS with this code.
- mediapipe on Pi OS. Bookworm ships Python 3.11, which mediapipe lists; Trixie ships
  3.13, which it doesn't list.
- Night driving: RGB can't see a hand in the dark, and MediaPipe is reported poor on
  IR images.
- Gear-knob grip and release can look like fist → open (pause).
- iOS may honour only the HID Play/Pause toggle (fallback: map both grabs to
  `play_pause`).
- iOS may hide the on-screen keyboard while a HID device is connected.
- Call answering on iPhone via HID is unlikely. HFP would risk stealing call audio
  from the car.

## How to work on this project

- Work **stage by stage**. After each stage, report what was built, how to test it,
  and what is still unverified, then stop for the user to test.
- Be upfront about anything that can't be verified without the real hardware. Flag it
  rather than guess.
- The user handles git themselves; don't run state-changing git commands.

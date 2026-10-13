# handGestureControl: notes for Claude

A car hand-gesture media controller. A camera watches a hand, gestures become media
commands, and a Raspberry Pi sends them to the phone over Bluetooth. User-facing docs,
the hardware list and mounting notes are in `README.md`; read it first.

## Locked decisions (ask before changing)

- **Bluetooth HID only.** The Pi is a Bluetooth **HID consumer-control device**
  (media keys) paired to the phone. It is NOT an A2DP sink, because that would pull
  phone audio away from the car stereo.
- **Phone:** iPhone 15, iOS 26.6.1.
- **Target hardware:** Raspberry Pi 4 **2 GB**, Raspberry Pi OS **(Legacy, 64-bit) Lite
  = Bookworm**, Python 3.11 (not Trixie: MediaPipe 1.x crashes on a Pi 4), headless
  (SSH only). **The Pi arrived 2026-10-10** with a **ribbon (CSI) camera**. Powered from a
  car USB charger.
- **Car:** right-hand drive, so the driver gestures with the **left hand** and the
  passenger with the right.
- **Portability:** the same code runs on the laptop and the Pi; board and camera
  differences live in `config/default.yaml`.
- **Model:** MediaPipe Hand Landmarker (Tasks API) in VIDEO mode, one hand, 320x240.
  Gestures are **rule-based geometry, not a trained model**: there is no training.
  Videos are for tuning thresholds and as regression tests.
- **Gesture design** (user's; works with either hand, directions as the user sees them).
  On 2026-10-13 the user switched to **static held poses**, because motion gestures
  were unreliable at the Pi's ~9 fps.
  - Five fingers up held: `pause` (`open_palm`).
  - Thumbs up: `play`.
  - Thumb pointing right / left: `next` / `previous`.
  - "Phone" hand (thumb + pinky out) held vertical: `answer_call`; held horizontal,
    either way round: `end_call`.
  - Index-finger circles clockwise / counter-clockwise: volume up / down (kept; they
    worked well). The first step needs 270° (lowered from 360° because clockwise felt
    hard), then one step per 180°.
  - Next / previous **repeat every 2 s while held** (`static.repeat_gestures`,
    `repeat_s`); the user asked for this on 2026-10-13.
  - `thumb_down` is unmapped. The old swipe and fist↔open gestures are still in the
    code but switched off (`null`) in the mapping.
- **Safety beats speed.**
  - Held poses fire once after `hold_s` (0.6 s) held still; movement restarts the hold.
  - Then they latch until something else is shown for `release_s`.
  - A 1 s global cooldown applies (repeated circling is exempt).
  - Hands that are too small, outside the active zone, or low-confidence are ignored.

## Status (2026-10-13)

| Stage | Status |
|---|---|
| 1 Vision (camera, landmarks) | Done. **Real Pi 4: ~9 FPS, ~110 ms inference**, ribbon camera via picamera2 |
| 2 Gestures, gating, YAML mapping, sample record/replay | Static poses + circles, tested live end to end on the Pi with the iPhone |
| 2b Real-camera videos: `record_video.py` (Pi), `evaluate_videos.py` (scoring) | Tools done; no in-car footage yet |
| 3 Action layer: `actions.py` (`print` / `bt_hid`) | Done |
| 4 BLE HID remote `gesturectl.hid` (BlueZ via dbus-fast) | Done. Paired and tested with the iPhone: every media key works |
| 5 Answering calls | **Investigate and report only**; a media remote has no answer key |
| 6 systemd services, rotating logs, install script | Built (`scripts/pi/`) |

On the Pi (2026-10-13):
- `scripts/pi/setup_bluetooth.sh` has been run: LE-only, `--noplugin=input`.
- The iPhone (shows as "T (2)") is bonded.

Waiting on the user:
- In-car footage per `docs/RECORDING.md`. Then evaluate with
  `--config config/car.yaml --fps 9`, tune, and run `--export-samples`.
- Check whether the iPhone's on-screen keyboard stays available while connected.
- **Left-hand clockwise circles are still hard; the right hand is fine** (user,
  2026-10-13). Desk clips: `videos/circle_cw_{left,right}_desk_1.mp4` (laptop and Pi,
  gitignored). Two causes found:
  - The index pointing toward the camera was read as curled, so the pose flipped to
    FIST/THUMB and the circle reset. **Fixed** by `geometry.index_pointing`
    (`point_straightness`, `point_min_alignment`): left clip 3/5 at `--fps 9`.
  - With `tracker.num_hands: 1` MediaPipe can lock onto a resting hand (e.g. at the
    chin, read as THUMB: a false `next` every 2 s). `num_hands: 2` gave left 4/5 and
    continuous circling on the right clip (0/5 with one hand), but costs 25 vs 14 ms
    per frame on the laptop. **Not adopted:** measure FPS on the Pi first; at ~5 fps
    circles may exceed `max_turn_deg`.
  - The Pi doesn't have the fix yet: after a push, `git pull`,
    `sudo scripts/pi/install_services.sh` (adds `gesturectl-tmux`), then
    `sudo systemctl restart gesturectl` (`enable --now` doesn't restart a running service).

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
python scripts/record_video.py videos/<label>_....mp4 --duration 45   # Pi, over SSH
python scripts/evaluate_videos.py --config config/car.yaml --fps 12 [--timeline] [--export-samples]
# Pi (over SSH, `ssh tk@gesturepi.local`; passwordless sudo works):
python -m gesturectl.hid status | send <action> | pair      # talk to the running remote
journalctl -u gesturectl -u gesturectl-hid -f               # live logs; files in logs/
sudo systemctl stop|start|restart gesturectl gesturectl-hid
tmux send-keys -t gesturectl '<cmd>' Enter                  # run where the user can watch
```
The user watches long-running Pi commands live with
`ssh -t tk@gesturepi.local tmux attach -r -t gesturectl`. Run them in that session.

## Code map and conventions

- **Pipeline:**
  `camera.py` (OpenCV, flip/rotate, centre-crop to 320x240)
  → `tracker.py` (MediaPipe → `HandFrame` in pixel units)
  → `engine.py` (gating → `geometry.classify_pose` → `PoseFilter` → recognizers in
  `gestures/` → cooldown → `mapping`)
  → `Event(gesture, action)`.
- `app.Pipeline` is shared by `__main__` and the recorder.
- **Actions.** `__main__` calls `actions.make_backend(cfg).send(action)`.
  - `print` on the laptop.
  - `bt_hid` (set in `car.yaml`) sends one line over TCP 127.0.0.1:47231 to the
    Bluetooth remote (`hid/protocol.py`).
  - The backend never raises; a missing service or phone is a rate-limited warning.
- **Bluetooth remote** (`python -m gesturectl.hid serve`):
  - `hid/keys.py`: report map, a 16-bit media-key bitmap with report ID 1;
    `media+keyboard` is a fallback profile.
  - `hid/bluez.py`: GATT objects, advertisement, agent.
  - `hid/service.py`: lifecycle and self-healing.
  - `hid/pairing.py`: the pairing window. New phones pair only while it's open: when
    nothing is bonded yet, or for 120 s after `pair`.
- **Services.** `scripts/pi/install_services.sh` installs `gesturectl-hid` and
  `gesturectl` (templates in `scripts/pi/`): `Restart=always`, `--log-file logs/*.log`
  (1 MB × 5). Stop `gesturectl` before `record_video.py`, because the camera is
  exclusive. If tmux is installed it also adds `gesturectl-tmux`, a oneshot that
  recreates the shared `gesturectl` tmux session at boot.
- **Camera source.** `camera.source: auto` (the default) uses picamera2 when it imports
  and finds a camera, else OpenCV. The same config works on the laptop and the Pi.
- **Videos.** In `video.py`: the filename is the label (`<gesture>_..._x3`, `none_`,
  `drive_`, `mixed_` plus a `.txt` of `m:ss gesture` lines).
  - The recorder saves **raw** frames plus a `.json` sidecar with real per-frame
    timestamps; cameras don't deliver even frame rates. The laptop webcam gave 18 fps
    against a nominal 30.
  - Landmarks are cached in `videos/.cache`, keyed on video, camera and tracker config,
    model, and `--fps`. Re-scoring after a threshold change is instant.
  - Scoring is in `evaluation.py`: circle steps less than 1.5 s apart are one
    repetition (`recording.count_reps` / `BURST_GAP_S`).
- **Units.** Thresholds are in **hand scales** (wrist → middle MCP) and **seconds**,
  never frames or pixels, so behaviour is the same at 10 FPS on the Pi and 30 FPS on
  the laptop.
- **Coordinates.** Image y points down, so a positive turn angle is clockwise on screen.
  `flip_horizontal: true` makes the image match the user's view on a facing camera.
- **Config.** Every tunable lives in `config/default.yaml` and mirrors the dataclass
  defaults in `config.py`; `test_default_yaml_matches_code_defaults` enforces this.
  Unknown keys are errors. `mapping:` replaces the default mapping entirely.
- **Per-machine overrides.** `--config X` is layered on top of `default.yaml`, merging
  key by key, so tuning done in default.yaml always carries over. `config/car.yaml`
  holds the car/Pi differences: `camera.rotate: 180` (the camera is mounted upside
  down; user decision 2026-10-13) and `actions.backend: bt_hid`. Always pass
  `--config config/car.yaml` on the Pi and when evaluating car videos.
- **Tests come first.** `tests/synth.py` builds 3D synthetic hands (any pose, size,
  rotation, left or right) and trajectories. Cover positive cases at 10 and 30 FPS with
  both hands, **plus negatives** (accidental-trigger cases).
- **Samples.** `samples/<label>/*.json` hold landmarks only (no images). They are
  regression test data and get committed. The `none` label means "must fire nothing".
- **Dependencies** are pinned in `requirements.txt`, with **two sets chosen by
  `platform_machine`**:
  - **Laptop** (not aarch64): mediapipe 1.0.1, numpy 2.4.6, opencv-contrib 5.0.
  - **Pi** (aarch64): mediapipe 0.10.18, numpy 1.26.4, opencv-contrib 4.11.0.86.

  **Code must work on both** (Python 3.11 and 3.13, numpy 1.x and 2.x). Before changing
  dependencies or tracker code, run the suite in `.venv-pi` (uv, Python 3.11, Pi
  versions; gitignored):
  `uv pip install --python .venv-pi/Scripts/python.exe "mediapipe==0.10.18" "opencv-contrib-python==4.11.0.86" "numpy==1.26.4" PyYAML pytest && .venv-pi/Scripts/python.exe -m pytest -q`.
  Use `opencv-contrib-python` (mediapipe depends on it); never also install
  `opencv-python`.

## Gotchas

- **mediapipe 1.0** is a ctypes wrapper; `mp.solutions` is gone.
  - Import with `from mediapipe.tasks.python import vision` and
    `from mediapipe.tasks.python.core.base_options import BaseOptions`.
  - `import mediapipe.tasks.python as tasks` fails.
- **The Pi 4 can't run MediaPipe 1.x.** The ARM builds need AES instructions the
  Cortex-A72 lacks: `FATAL ERROR: This binary was compiled with aes enabled` /
  `Illegal instruction`, seen 2026-10-13.
  - 0.10.18 is the last ARM build without that requirement, for cp39–cp312 only.
  - Hence Raspberry Pi OS **Bookworm** (Python 3.11), not Trixie (3.13).
  - All its dependencies have aarch64 cp311 wheels (checked).
  - The vision API doesn't import jax/jaxlib.
- **Pi system libraries** that mediapipe and OpenCV need on Lite: `libportaudio2`,
  `libgl1`, `libgles2`, `libegl1`. `import mediapipe` alone doesn't load the native
  engine; only creating a `HandLandmarker` does, so check with that.
- **Laptop cameras.** The laptop webcam delivers 640x360 natively, which is
  centre-cropped to 4:3. The laptop also has an IR camera, so check `camera.index`.
- **picamera2** comes from apt only. On the Pi, the venv needs
  `--system-site-packages`. Its `RGB888` format is BGR in memory, which OpenCV wants.
  On Bookworm it's built against numpy 1.x, which matches the Pi pin (1.26.4).
  Verified on the real Pi (Trixie, 2026-10-13): `auto` picked it and it streamed
  320x240.
- **mediapipe logging.** The `W0000 ... inference_feedback_manager` stderr line is
  harmless noise. `GLOG_minloglevel` doesn't silence it.
- **dbus-fast** (Pi only; requirements marker `sys_platform == "linux"`).
  - Its `ServiceInterface` keeps the D-Bus interface name in **`self.name`**. Never
    assign `self.name` in a subclass: that renamed our characteristics and BlueZ
    rejected the app ("No valid service object found"). Use `self.label`.
  - It reads D-Bus signatures from annotations at runtime, so `hid/bluez.py` must
    not use `from __future__ import annotations`.
  - Decorators are `dbus_method` / `dbus_property`.
  - `GetManagedObjects` is answered automatically, but only for objects *below* the
    requested path. Hence the GATT app lives at `/gesturectl/gatt`, with the
    advertisement and agent outside it.
  - Only root may call into our process on the system bus (debug with `sudo busctl`).
- **iOS + BLE HID** (tested on an iPhone 15 / iOS 26.6.1):
  - **Volume keys are ignored at a 30 ms press; 150 ms works** (`hid.key_press_s`).
  - Separate play (0xB0) and pause (0xB1) work.
  - A bonded iPhone that stays connected while the service restarts may **not**
    re-subscribe to the report. BlueZ then silently drops the notifications.
    `service.watch()` disconnects a phone that is connected but not subscribed for
    more than 6 s; the iPhone reconnects within ~3 s and re-subscribes. "Keys
    ready" means subscribed (StartNotify), never just connected.
  - Encrypted-read flags on the HID info, report map and report make the iPhone pair
    ("Just Works", NoInputNoOutput agent).
  - LE-only mode plus `--noplugin=input` are required, or iOS prefers Classic.

## Unverified / risks to keep flagging

- Autostart after a real reboot, and how long the iPhone takes to reconnect in the car.
- SD card corruption from car power cuts: no read-only overlay yet.
- Night driving: RGB can't see a hand in the dark, and MediaPipe is reported poor on
  IR images.
- Gear-knob grip and release; quick thumbs-up or raised hands to other drivers
  (could trigger play/pause).
- iOS may hide the on-screen keyboard while the remote is connected (unchecked).
- Call answering on iPhone via HID is unlikely. HFP would risk stealing call audio
  from the car.

## How to work on this project

- Work **stage by stage**. After each stage, report what was built, how to test it,
  and what is still unverified, then stop for the user to test.
- Be upfront about anything that can't be verified without the real hardware. Flag it
  rather than guess.
- The user handles git themselves; don't run state-changing git commands unless they
  ask in that message. On the Pi, test uncommitted code in `~/gesturectl-dev` (via
  `PYTHONPATH=~/gesturectl-dev/src`), not in the git clone `~/hand-gesture-control`.

# Raspberry Pi setup

Target hardware is a Raspberry Pi 4 with a ribbon (CSI) camera, running headless over
SSH. Steps marked **(unverified)** haven't been tried on real hardware yet; if one
fails, note the exact error message.

Bluetooth (Stage 4) will be added to this file later.

## 1. Flash the SD card (on your laptop)

1. Install **Raspberry Pi Imager** from raspberrypi.com/software.
2. Choose **Device:** Raspberry Pi 4. **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS
   Lite (64-bit)**. **Storage:** your microSD card.
3. When asked about OS customisation, choose **Edit settings**:
   - **Hostname:** `gesturepi`
   - **Username and password:** your choice; you'll type these when you SSH in.
   - **Wireless LAN:** your home Wi-Fi, country `TH`.
   - **Locale:** time zone `Asia/Bangkok`.
   - **Services** tab: **Enable SSH** (password authentication is fine).
4. Write the card.

*Which OS version:* the current Lite image is Debian "Trixie" with Python 3.13. Use it.
mediapipe ran on Python 3.13 on the laptop, and Trixie's system numpy is 2.x, which
matches this project. Fall back to the older **Bookworm** (Legacy) image only if
mediapipe won't import in step 4. On Bookworm, picamera2 may conflict with numpy 2
**(unverified)**.

## 2. Connect the camera (Pi switched off)

1. Find the **CAMERA** connector between the HDMI ports and the audio jack.
2. Gently lift the plastic latch.
3. Insert the ribbon with the **metal contacts facing the HDMI ports** (blue tab toward
   the USB/Ethernet ports).
4. Press the latch down.

The ribbon must be straight and fully inserted. Most "no camera found" problems are the
ribbon.

## 3. First boot and system packages

Insert the card, power the Pi, and wait about 2 minutes. Then, from your laptop:

```bash
ssh <user>@gesturepi.local
sudo apt update && sudo apt full-upgrade -y
sudo reboot
sudo apt install -y git python3-venv python3-picamera2 libportaudio2 libgl1
```

Why each package:

| Package | Why |
|---|---|
| `python3-picamera2` | The ribbon-camera library. It only installs from apt, not pip. |
| `libportaudio2` | mediapipe imports an audio library at start-up. |
| `libgl1` | The OpenCV build that mediapipe requires needs it, even on a headless Pi. |

Check the camera, then take a snapshot so you can see where it's aimed:

```bash
rpicam-hello --list-cameras        # should list one camera, e.g. ov5647
rpicam-still -n -o aim.jpg --width 640 --height 480 -t 2000   # -n: no preview window (no screen)
```

Copy the snapshot to your laptop. In PowerShell, inside the project folder:

```powershell
scp <user>@gesturepi.local:aim.jpg .
```

## 4. Install the project

```bash
git clone https://github.com/TK-06/hand-gesture-control.git
cd hand-gesture-control
python3 -m venv --system-site-packages .venv   # system packages: so picamera2 (from apt) is visible
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python scripts/download_model.py
python -c "import mediapipe, cv2, picamera2; print('imports ok')"
```

The first `pip install` takes a few minutes; mediapipe and OpenCV are large.

## 5. First run on the Pi

```bash
python -m gesturectl --config config/car.yaml --no-window --duration 30
```

The first log line should say `picamera2 camera 0: 320x240`. That means `camera.source:
auto` found the ribbon camera. Every 5 s it logs FPS and inference time, which are the
first real Pi 4 numbers. Hold your hand in front of the camera during the run so the
"hand in N% of frames" figure means something. **Note the FPS:** you'll pass it to the
video evaluator as `--fps`.

## 6. Recording test videos

See [RECORDING.md](RECORDING.md) for the shot list. Each recording is one command over
SSH:

```bash
cd ~/hand-gesture-control && source .venv/bin/activate
python scripts/record_video.py videos/swipe_left_driver_day_1.mp4 --duration 45
```

It counts down 3 seconds, then records. Ctrl+C stops early.

**In the car**, there is no home Wi-Fi:
1. Turn on your iPhone's **Personal Hotspot**.
2. Add the hotspot to the Pi once, while still at home:
   `sudo nmcli dev wifi connect "<hotspot name>" password "<password>"`.
3. SSH from your laptop on the same hotspot, or from the phone with an SSH app such as
   Termius.

Power the Pi from a 5 V / 3 A car charger or a power bank. Under-voltage causes dropped
frames: `vcgencmd get_throttled` should print `throttled=0x0`.

## 7. Copy videos to the laptop and evaluate

In PowerShell, inside the project folder:

```powershell
scp -r <user>@gesturepi.local:~/hand-gesture-control/videos .
python scripts/evaluate_videos.py --config config/car.yaml --fps <Pi FPS from step 5>
```

`videos/` is in `.gitignore`: recordings stay private and are never pushed.

## Troubleshooting

| Symptom | Try |
|---|---|
| `ssh: Could not resolve hostname gesturepi.local` | Wait another minute; check the Wi-Fi details in Imager; or use the Pi's IP address from your router's device list. |
| `rpicam-hello` lists no cameras | Power off, reseat the ribbon at both ends (contacts toward HDMI on the Pi side). |
| `ImportError: libGL.so.1` | `sudo apt install -y libgl1` |
| `ImportError` mentioning `libgthread` / `libglib` | `sudo apt install -y libglib2.0-0t64` (Trixie) or `libglib2.0-0` (Bookworm) |
| `OSError: PortAudio library not found` | `sudo apt install -y libportaudio2` |
| `picamera2 is not importable` | `sudo apt install -y python3-picamera2`, and the venv must be created with `--system-site-packages` |
| numpy errors when importing picamera2 | You're probably on Bookworm (numpy 1.x system packages). Use the Trixie image. |
| Low FPS / `throttled=0x5...` | Power supply too weak, or the Pi is hot. Use a 3 A supply and a heatsink case. |

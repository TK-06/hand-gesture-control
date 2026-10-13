# Raspberry Pi setup: step by step

This takes a blank SD card to a Raspberry Pi 4 that runs the gesture controller with
its ribbon camera, headless over SSH. Plan about **1 hour**, mostly waiting for
downloads.

How to read this guide:

- **Laptop (PowerShell):** run the command in PowerShell on your laptop.
- **Pi:** run it in the SSH window, where the prompt looks like `<user>@gesturepi:~ $`.
- **✅ Expect:** what you should see if the step worked. If you see something else,
  check [Troubleshooting](#troubleshooting) at the bottom.
- Replace `<user>` with the username you choose in step 1.

---

## 0. One time only: an SSH key on the laptop (2 min)

The key lets you log in without a password, and lets Claude run commands on the Pi
for you. If `C:\Users\<you>\.ssh\id_ed25519.pub` already exists, skip this step.

**Laptop (PowerShell):**
```powershell
ssh-keygen -t ed25519      # press Enter at every question
```

---

## 1. Flash the SD card (on the laptop, ~10 min)

1. Install **Raspberry Pi Imager** for **Windows** from raspberrypi.com/software. It runs
   on the laptop; the Pi's Linux system is chosen inside it.
2. Put the SD card in the laptop. In Imager choose:
   - **Device:** Raspberry Pi 4
   - **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS (Legacy, 64-bit) Lite**. This
     is Debian "Bookworm". **Not** the default "Raspberry Pi OS Lite": see the box below.
   - **Storage:** your SD card
3. Copy your public key to the clipboard. **Laptop (PowerShell):**
   ```powershell
   Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
   ```
4. In the customisation settings (screens differ a little between Imager versions):

   | Setting | Value |
   |---|---|
   | Hostname | `gesturepi` |
   | Username / password | your choice. The password is needed for `sudo` commands, so remember it. |
   | Wi-Fi | your home network, country `TH` |
   | Time zone | `Asia/Bangkok` |
   | SSH | enabled, **public-key only**. Paste with Ctrl+V. It must start with `ssh-ed25519 AAAA`. |
   | Raspberry Pi Connect | leave **off** (not needed; SSH covers it) |

5. Write the card. It erases everything on it.

✅ **Expect:** "Write successful".

> **Paste the key, not the fingerprint.** `ssh-keygen` also prints a line starting
> with `SHA256:...`. That's the fingerprint; pasting it gives
> `Permission denied (publickey)` later. The command in step 3 copies the right thing.

> **Why Bookworm (Legacy), not Trixie.** MediaPipe 1.x for ARM is compiled to use AES
> crypto instructions. The Pi 4's processor (Cortex-A72) doesn't have them, so it
> crashes with `FATAL ERROR: This binary was compiled with aes enabled`. The last
> MediaPipe that runs on a Pi 4 is **0.10.18**, and it only exists for Python 3.9–3.12.
> Trixie has Python 3.13; Bookworm has **3.11**. `requirements.txt` installs
> mediapipe 0.10.18 (with numpy 1.26 and OpenCV 4.11) automatically on the Pi. This
> combination was tested on the laptop under Python 3.11: all tests pass, and it gives
> the same hand landmarks as the laptop's MediaPipe 1.0.1.

---

## 2. Connect the camera (Pi unplugged)

1. On the Pi, find the **CAMERA** connector between the micro-HDMI ports and the audio
   jack.
2. Gently lift its plastic latch.
3. Slide the ribbon in with the **metal contacts facing the HDMI ports** (blue tab
   toward the USB/Ethernet ports).
4. Press the latch down.

Check the other end at the camera board too. The ribbon must be straight and fully in;
most "no camera" problems are the ribbon.

---

## 3. First boot and log in (~3 min)

1. Put the SD card in the Pi and plug in power (USB-C, 5 V / 3 A).
2. **Wait 2–3 minutes.** The first boot sets itself up and restarts once.
3. **Laptop (PowerShell):**
   ```powershell
   ssh-keygen -R gesturepi.local     # forget any previous Pi with this name (needed after a reflash)
   ssh <user>@gesturepi.local
   ```
4. Type **`yes`** when asked *"Are you sure you want to continue connecting?"*.

✅ **Expect:** the prompt changes to `<user>@gesturepi:~ $`, with no password asked. All
**Pi:** commands from here on go in this window.

---

## 4. System packages and camera check (~10–15 min)

**Pi:**
```bash
sudo apt update && sudo apt full-upgrade -y
```
`sudo` asks for **your password** (the one from Imager). Nothing appears while you type
it; that's normal. This updates the whole system.

If the output mentions a **new kernel** (`linux-image-...` being installed), restart and
reconnect: `sudo reboot`, wait 1 minute, then `ssh <user>@gesturepi.local` again. If it
only updated a few small packages, skip the reboot.

**Pi:**
```bash
sudo apt install -y git python3-venv python3-picamera2 libportaudio2 libgl1 libgles2 libegl1
rpicam-hello --list-cameras
```

| Package | Why |
|---|---|
| `git` | to download the project |
| `python3-venv` | to give the project its own Python environment |
| `python3-picamera2` | the ribbon-camera library (apt only, not pip) |
| `libportaudio2` | mediapipe loads an audio library at start-up |
| `libgl1`, `libgles2`, `libegl1` | graphics libraries OpenCV and mediapipe's engine need, even on a Pi with no screen. Lite doesn't include them. |

✅ **Expect:** `rpicam-hello` lists one camera, like `0 : ov5647 [2592x1944 ...]`.

**Optional, see the camera's view.** Take a photo. It waits 5 s, so you can get into
position, and `--rotation 180` turns it upright for an upside-down mount:

**Pi:**
```bash
rpicam-still -n -o aim.jpg --width 640 --height 480 -t 5000 --rotation 180
```
**Laptop (PowerShell)**, inside the project folder. Mind the **`.`** at the end:
```powershell
scp <user>@gesturepi.local:aim.jpg .
```
Run the same two commands again to retake it. `*.jpg` is in `.gitignore`, so the photo
is never pushed.

---

## 5. Install the project (~10 min)

**Pi:**
```bash
git clone https://github.com/TK-06/hand-gesture-control.git
cd hand-gesture-control
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python --version
```
✅ **Expect:** the prompt now starts with `(.venv)`, and the version is **Python
3.11.x**. If it says 3.13, you flashed the wrong OS; go back to step 1.

`--system-site-packages` lets the project see the camera library installed by apt.

**Pi:**
```bash
pip install -r requirements.txt
pip install -e .
python scripts/download_model.py
```
✅ **Expect:** `Successfully installed ... mediapipe-0.10.18 ... numpy-1.26.4 ...
opencv-contrib-python-4.11.0.86 ...`, then `Saved .../models/hand_landmarker.task`.

These messages during `pip install` are **harmless**:
- *"Not uninstalling … outside environment"*: pip leaves the system's own copies alone
  and installs ours inside `.venv`.
- *"ERROR: pip's dependency resolver … types-seaborn requires pandas-stubs"*: this is
  about a package Raspberry Pi OS ships for itself, unrelated to us. Nothing failed.

Final check: this actually starts the hand tracker. A plain `import mediapipe` would
not catch missing system libraries.

**Pi:**
```bash
python -c "import picamera2; from gesturectl.config import load_config; from gesturectl.tracker import HandTracker; c = load_config(); HandTracker(c.tracker, c.model_path()).close(); print('hand tracker ok')"
```
✅ **Expect:** `hand tracker ok` (possibly after some `INFO`/`W0000` log lines, which are
fine).

---

## 6. First run (1 min)

**Pi:**
```bash
python -m gesturectl --config config/car.yaml --no-window --duration 60
```
`config/car.yaml` holds the car settings, layered on `config/default.yaml`: it rotates
the upside-down camera and sends actions to the Bluetooth remote (step 7). Until that
runs, the log says the remote isn't reachable; that's expected.

While it runs, hold your hand **30–60 cm** from the camera and do these, pausing a few
seconds between each:

| Do this | ✅ Look for |
|---|---|
| Hold an open hand still for a few seconds | `hand in N% of frames` goes up |
| Index finger only, **slow circles clockwise** (first step after ¾ of a circle) | `ACTION volume_up` |
| Same, **counter-clockwise** | `ACTION volume_down` |
| Hold **five fingers up** still ~1 s | `ACTION pause` |
| Hold a **thumbs up** still ~1 s | `ACTION play` |
| Fist with the **thumb pointing to your right** / **left**, held ~1 s | `ACTION next` / `ACTION previous` (keep holding: again every 2 s) |
| **Phone hand** (thumb + pinky out) held **upright**, ~1 s | `ACTION answer_call` |
| Phone hand held **sideways**, ~1 s | `ACTION end_call` |

Directions are as **you** see them. Each held pose fires once; lower your hand before
repeating it.

✅ **Expect:**
- a line containing `picamera2 camera 0: 320x240`, which means the ribbon camera is in
  use;
- every 5 s, a line like `9.8 fps, inference 85 ms, hand in 60% of frames`.

**Write down the FPS.** It's the first real Pi 4 number, and you'll pass it to the
video evaluator as `--fps`. Don't worry if some gestures don't fire yet; thresholds
get tuned on your real videos next.

---

## 7. Bluetooth: set up and pair your iPhone (~10 min)

The Pi becomes a **Bluetooth LE media remote** called "Gesture Remote". It only sends
media keys (volume, play, pause, next, previous). Your phone keeps playing through the
car stereo as usual.

**One-time Bluetooth setup. Pi:**
```bash
cd ~/hand-gesture-control && source .venv/bin/activate
pip install -r requirements.txt                 # adds dbus-fast (talks to BlueZ)
sudo scripts/pi/setup_bluetooth.sh
```
✅ **Expect:** `done: Bluetooth LE only, input plugin off`.

What the setup script changes, and why:
- **bluetoothd without its "input" plugin, and the controller in Bluetooth LE-only
  mode.** Otherwise iPhones try to connect the old (Classic) way and the remote
  doesn't work. The Pi doesn't need Classic Bluetooth for anything here.
- **`JustWorksRepairing = always`**, so a phone that did "Forget This Device" can pair
  again.

`sudo scripts/pi/setup_bluetooth.sh --undo` puts it all back.

**Start the remote.** Step 8 makes this automatic; to try it by hand first. **Pi:**
```bash
python -m gesturectl.hid --config config/car.yaml serve
```
✅ **Expect:** `no phone paired yet: pairing is open until one pairs` and
`advertising as 'Gesture Remote'`.

**Pair.**
1. **iPhone:** Settings → Bluetooth.
2. Tap **Gesture Remote** (under Other Devices), then **Pair**.

✅ **Expect:** it moves to My Devices as **Connected**, and the Pi logs
`phone subscribed to media keys` and then `pairing window closed`.

**Test each key** from a second SSH window while music plays on the phone. **Pi:**
```bash
python -m gesturectl.hid status                 # connected: iPhone; ...; keys ready: yes
python -m gesturectl.hid send volume_up         # also: volume_down pause play next previous play_pause
```
Each command prints `ok` when the key was sent.

**Security: only one pairing window.** Once a phone is paired, the remote refuses *new*
phones, so nobody in the next car can pair with it. To add another phone (for example
a passenger's), open a 2-minute window first:
```bash
python -m gesturectl.hid pair
```

**Tested on an iPhone 15 with iOS 26.6.1:**
- volume up/down, play, pause, play/pause, next and previous all work;
- volume keys need a ~150 ms key press (iOS ignores shorter taps), which is the
  default.

Calls can't be answered this way: phones only take call controls over the hands-free
connection, which this remote deliberately doesn't use. The phone gestures are
recognized but do nothing yet.

---

## 8. Start automatically at boot

**Pi:**
```bash
cd ~/hand-gesture-control
sudo scripts/pi/install_services.sh
```
This installs services that start at every boot. The first two restart by themselves
if they ever stop:

| Service | What it does |
|---|---|
| `gesturectl-hid` | the Bluetooth remote; keeps the phone connected |
| `gesturectl` | camera + gesture recognition; sends actions to `gesturectl-hid` |
| `gesturectl-tmux` | the shared terminal session for watching live (step 10); only if tmux is installed |

✅ **Expect:** `gesturectl-hid` and `gesturectl` show `Active: active (running)`.
`gesturectl-tmux` shows `active (exited)`, which is normal: it only creates the session.

From then on there's nothing to type. Power on the Pi; about 30–60 s later your iPhone
reconnects by itself (with Bluetooth on) and gestures work.

**Staying connected:**
- The remote keeps Bluetooth powered and keeps advertising whenever no phone is
  connected, so the iPhone can always find it again.
- If the phone ends up connected but not listening for keys (for example after the
  remote restarts while the phone stays connected), the remote drops the link on
  purpose. The iPhone reconnects within a few seconds.

`sudo scripts/pi/install_services.sh --uninstall` stops and removes all of them.

---

## 9. Everyday use

| What | Command (**Pi**, unless noted) |
|---|---|
| Log in | **Laptop:** `ssh <user>@gesturepi.local` |
| Start of every session | `cd ~/hand-gesture-control && source .venv/bin/activate` |
| Is the phone connected? | `python -m gesturectl.hid status` |
| Services running? | `systemctl status gesturectl gesturectl-hid` |
| Stop / start gestures (e.g. to record videos) | `sudo systemctl stop gesturectl` / `sudo systemctl start gesturectl` |
| Pair another phone | `python -m gesturectl.hid pair` |
| Get the latest code (after a push from the laptop) | `git pull && pip install -r requirements.txt && sudo systemctl restart gesturectl-hid gesturectl` |
| Shut down: **always** before unplugging at your desk | `sudo poweroff`, then wait for the green light to stop blinking |

---

## 10. Watch it live

**Logs as they happen.** **Pi:**
```bash
journalctl -u gesturectl -u gesturectl-hid -f      # Ctrl+C to stop watching
```
The same logs are also saved, rotating at 1 MB × 5, in `~/hand-gesture-control/logs/`
(`gesturectl.log`, `hid.log`). That's how you see afterwards what happened on a drive.

**Watch what Claude runs on the Pi.** Claude runs long commands inside a shared terminal
session called `gesturectl`, which is created at every boot. To watch it read-only, so
you can't type into it by accident. **Laptop (PowerShell):**
```powershell
ssh -t <user>@gesturepi.local tmux attach -r -t gesturectl
```
Leave it with **Ctrl+B**, then **D**. The session keeps running.

If it says `can't find session`, run `sudo scripts/pi/install_services.sh` once on the
Pi: installs from before this was added don't have the service that creates it.

---

## 11. Recording test videos

See [RECORDING.md](RECORDING.md) for the shot list. The camera can only be used by one
program at a time, so **stop the gesture service first** and start it again afterwards.
**Pi:**
```bash
sudo systemctl stop gesturectl
python scripts/record_video.py videos/thumb_left_driver_day_1.mp4 --duration 45
sudo systemctl start gesturectl
```
`record_video.py` counts down 3 seconds, then records. Ctrl+C stops early. Frames are
saved raw, so the rotation from `car.yaml` is applied later, when evaluating.

**In the car** there's no home Wi-Fi:
1. Turn on your iPhone's **Personal Hotspot**.
2. Add the hotspot to the Pi once, while still at home. **Pi:**
   `sudo nmcli dev wifi connect "<hotspot name>" password "<password>"`
3. Connect the laptop to the same hotspot and SSH in as usual. A phone with an SSH app
   such as Termius also works, but needs its own key.

Power the Pi from a **5 V / 3 A** car charger or a power bank. Under-voltage causes
dropped frames: **Pi:** `vcgencmd get_throttled` should print `throttled=0x0`.

---

## 12. Copy videos to the laptop and evaluate

**Laptop (PowerShell)**, inside the project folder:
```powershell
scp -r <user>@gesturepi.local:~/hand-gesture-control/videos .
python scripts/evaluate_videos.py --config config/car.yaml --fps <your FPS from step 6>
```
`videos/` is in `.gitignore`: recordings stay private and are never pushed.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Imager: *"Error writing to storage device"* | Close Imager, unplug and replug the card reader, try again. Then try: Imager → OS → **Erase** first, a different USB port (not a hub), running Imager as administrator, another reader, another card. |
| `Permission denied (publickey)` | The Pi doesn't have your key. Usually the **fingerprint** (`SHA256:...`) was pasted instead of the key. Reflash, using the `Set-Clipboard` command from step 1. Also check the username. |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` | Normal after a reflash. **Laptop:** `ssh-keygen -R gesturepi.local`, then ssh again. |
| `ssh: Could not resolve hostname gesturepi.local` | Wait another minute; check the Wi-Fi details in Imager; or use the Pi's IP address from your router's device list. |
| `[sudo] password for <user>:` | Type the Imager password; nothing shows while typing. Forgot it? There's no recovery: reflash with a new password (the key can stay). |
| `scp` prints only a `usage:` message | The destination is missing: add ` .` at the end of the command. |
| `rpicam-hello` lists no cameras | `sudo poweroff`, unplug, reseat the ribbon at both ends (contacts toward HDMI on the Pi side). |
| `FATAL ERROR: This binary was compiled with aes enabled` / `Illegal instruction` | MediaPipe 1.x got installed, and the Pi 4 can't run it. `python --version` in the venv must say 3.11. If it's 3.13 (Trixie), reflash with the Legacy (Bookworm) image. |
| `No matching distribution found for mediapipe==0.10.18` | Python is 3.13 (Trixie). Reflash with Raspberry Pi OS (Legacy, 64-bit) Lite. |
| `OSError: libGLESv2.so.2` or `libEGL.so.1: cannot open shared object file` | `sudo apt install -y libgles2 libegl1` |
| `ImportError: libGL.so.1` | `sudo apt install -y libgl1` |
| `ImportError` mentioning `libgthread` / `libglib` | `sudo apt install -y libglib2.0-0` |
| `OSError: PortAudio library not found` | `sudo apt install -y libportaudio2` |
| `picamera2 is not importable` | `sudo apt install -y python3-picamera2`, and the venv must be created with `--system-site-packages` |
| numpy errors when importing picamera2 | numpy 2 ended up in the venv: `pip install "numpy==1.26.4"` |
| Low FPS / `throttled=0x5...` | Power supply too weak, or the Pi is hot. Use a 3 A supply and a heatsink case. |
| "Gesture Remote" doesn't appear on the iPhone | Is the remote running (`python -m gesturectl.hid status`)? Once a phone is paired, new phones only see it during `python -m gesturectl.hid pair`. |
| Log says `Bluetooth remote service not reachable` | `gesturectl-hid` isn't running: `sudo systemctl start gesturectl-hid`, then check `journalctl -u gesturectl-hid`. |
| `error: phone not connected` | iPhone Bluetooth is off, or the phone is out of range. It reconnects by itself when back. |
| `error: phone connected but not listening for keys yet` | Wait ~20 s: the remote reconnects the phone automatically. |
| Keys arrive but volume doesn't change | Check `hid.key_press_s` is 0.15 (iOS ignores shorter volume taps). |
| After "Forget This Device" the iPhone can't pair again | `python -m gesturectl.hid pair`, then pair within 2 minutes. |
| Camera busy / `record_video.py` can't open the camera | The gesture service has it: `sudo systemctl stop gesturectl` first. |

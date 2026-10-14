# Recording test videos

These videos are **not training data**: the gestures are geometry rules, not a trained
model. They're used to:

- **tune thresholds** against your real camera, mount, lighting and hands;
- **measure accidental triggers** in normal driving, which matters most for safety;
- **become regression tests:** once a clip behaves correctly, `--export-samples` turns
  it into a small landmark file in `samples/` that `pytest` checks on every run.

Videos stay in `videos/` (gitignored, never pushed).

**First car session:** follow the [car session checklist](#car-session-checklist) from
top to bottom. It records the priority clips (A, D and G): about 30 minutes parked plus
a 25-minute drive, roughly 1.2 GB.

Where to run each command, as in [SETUP.md](SETUP.md):
- **Pi:** in your SSH session on the Pi.
- **Laptop (PowerShell):** on the laptop, inside the project folder.

---

## Car session checklist

### 1. At home, once: save your iPhone hotspot on the Pi

In the car there's no home Wi-Fi, so the Pi and the laptop meet on your iPhone's
Personal Hotspot.

1. **iPhone:** Settings → **Personal Hotspot** → turn on **Allow Others to Join**, and
   **stay on that screen**. Other devices only see the hotspot while that screen is open
   (or just after you turn it on in Control Centre).
2. **Pi** (SSH in at home as usual): find the hotspot's exact name.
   ```bash
   sudo nmcli -f SSID,SIGNAL dev wifi list --rescan yes
   ```
   Copy the name exactly as listed. iPhone names often contain a curly apostrophe (’)
   that's hard to type.
   Not in the list? Turn on **Maximise Compatibility** on the same iPhone screen (the
   hotspot switches to 2.4 GHz) and run it again.
3. **Pi:** save the hotspot. This only saves it; the Pi stays on your home Wi-Fi.
   ```bash
   read -rsp "Hotspot password: " PSK; echo
   sudo nmcli connection add type wifi con-name car-hotspot ifname wlan0 ssid "<exact name>" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK"
   unset PSK
   ```
   The password doesn't show while you type it; press Enter at the end.
   `nmcli connection show` should now list `car-hotspot`.
   Made a typo? `sudo nmcli connection delete car-hotspot`, then save it again.
4. **Test it at home.** This takes 2 minutes and saves trouble in the car.
   - Hotspot on, Personal Hotspot screen open. **Pi:**
     `sudo nmcli connection up car-hotspot`. Your SSH session freezes. That's expected:
     the Pi just moved to the hotspot. Close that window.
   - Connect the laptop to the hotspot too. **Laptop:** `ssh tk@gesturepi.local`. If
     you get in, it works.
   - Turn the hotspot off. Within a minute or two the Pi and the laptop go back to your
     home Wi-Fi by themselves.

   **Can't reach the Pi on the hotspot?**
   - Turn the hotspot off; the Pi returns to home Wi-Fi by itself. Check the name and
     password, then save the hotspot again.
   - If only the name `gesturepi.local` fails, find the Pi by its address: see
     [Can't reach the Pi](SETUP.md#cant-reach-the-pi-could-not-resolve-hostname-gesturepilocal)
     in SETUP.md, with `$net = "172.20.10"`.

### 2. Pack

- The Pi, camera and mount.
- A **power bank**: USB-C, 5 V / 3 A, plus a good cable. Don't use the car's USB yet: it
  cuts out the moment you switch off the engine, which can corrupt the SD card (fixed
  later, in roadmap Stage 8).
- The laptop, charged, and the iPhone.
- Plan for daylight: about 30 minutes parked, then a 25-minute drive.

### 3. In the car, parked: start up

1. **iPhone:** open the Personal Hotspot screen. **Laptop:** join the hotspot.
2. Plug the Pi into the power bank. After about a minute it's on the hotspot, and the
   iPhone reconnects to "Gesture Remote" by itself.
3. **Laptop:** `ssh tk@gesturepi.local`. `Could not resolve hostname`? Wait another
   minute, then follow
   [Can't reach the Pi](SETUP.md#cant-reach-the-pi-could-not-resolve-hostname-gesturepilocal)
   in SETUP.md (on the hotspot, use `$net = "172.20.10"`).
4. **Pi:** check the power, then work inside tmux, so a dropped connection can't stop a
   recording.
   ```bash
   vcgencmd get_throttled            # must say throttled=0x0; anything else: the power bank is too weak
   tmux new -A -s gesturectl         # everything in here keeps running if the laptop disconnects
   cd ~/hand-gesture-control && source .venv/bin/activate
   sudo systemctl stop gesturectl    # frees the camera; gestures are off while recording
   ```
   Lost the connection? SSH in again and run `tmux attach -t gesturectl` to get back to
   where you were.

### 4. Mount and aim the camera

Fix the camera in its final mount (see "Mounting notes" in the [README](../README.md)).
Then take a test photo. The photo is taken 3 seconds after you press Enter, so hold your
left hand where you'd gesture. **Pi:**
```bash
rpicam-still -n -o ~/aim.jpg --width 640 --height 480 -t 3000 --rotation 180
```
**Laptop**, in a second PowerShell window:
```powershell
scp tk@gesturepi.local:aim.jpg . ; Invoke-Item aim.jpg
```
The photo should show:
- **Your hand** in its natural gesture spot (near the wheel, in front of the centre
  stack), fully inside the picture, with room around it for circles.
- **A big enough hand.** Wrist to fingertips should be at least a fifth of the picture's
  height; a quarter to a half is ideal. Smaller hands are ignored.
- **The right way up:** up in the photo is up in the car. If it's upside down, note it:
  that's one setting (`camera.rotate`) in `config/car.yaml`.
- **If possible:** no side windows (sun glare, hands outside the car) and no gear lever
  (gripping it looks like a fist).
- **For later passenger clips (B):** the passenger's hand spot in view too.

Adjust and retake until it looks right. **Then don't move the camera** for the rest of
the session. If it gets bumped, re-aim it and make a note.

### 5. Record the parked clips: A, then D

Read the [rules while recording](#rules-while-recording) once. Then run the commands
under **A** and **D** in the shot list below, one at a time. Each command:
- counts down 5 seconds, which gives you time to put the laptop down and get ready;
- records for the set time and stops by itself;
- prints `saved videos/<name>.mp4 (… MB)`.

Messed one up? Run the same command again with `--force` added at the end; it
overwrites the old clip.

This takes about 25 minutes.

### 6. Drive: G

While still parked, start the recording. **Pi:**
```bash
python scripts/record_video.py videos/drive_day_1.mp4 --split 300 --duration 1500 --countdown 5
```
Then put the laptop away; closing the lid is fine, because the recording runs on the Pi.
Drive normally for about 25 minutes, **without any gestures**. It saves a new file every
5 minutes and stops by itself after 25 minutes.

Shorter drive? Afterwards, SSH in, run `tmux attach -t gesturectl` and press Ctrl+C.
Everything recorded so far is kept.

Gestures are off during the drive (the service is stopped), so nothing is sent to the
iPhone.

### 7. Finish, parked

**Pi:**
```bash
ls -lh videos                      # every clip is there
sudo systemctl start gesturectl    # gestures back on
```
**Optional:** try each gesture while music plays through the car, to check it works with
the car's audio. To watch what's detected: `journalctl -u gesturectl -f` (Ctrl+C stops
watching).

Then **shut down before unplugging. Pi:**
```bash
sudo poweroff
```
Wait until the Pi's green light stops flashing (about 20 s), then unplug the power bank.
Don't leave the Pi in a parked car in the sun: it's rated for 0–50 °C.

### 8. Back home: copy the videos

Plug the Pi into its normal power; it rejoins your home Wi-Fi within 1–2 minutes (can't
connect? see [Can't reach the Pi](SETUP.md#cant-reach-the-pi-could-not-resolve-hostname-gesturepilocal)).
**Laptop** (about 1 GB, a few minutes):
```powershell
scp -r tk@gesturepi.local:~/hand-gesture-control/videos .
```
Then [check your recordings](#check-your-recordings), or ask Claude to evaluate them and
tune whatever misfires.

---

## Rules while recording

- **Keep the camera where it is.** Don't move it between clips. If you do move it,
  mention it.
- **Gesture clips: park the car.** Never test gestures while driving. Only the `drive_`
  takes are recorded while driving, and in those you don't do any gestures.
- **Between repetitions,** put your hand back where it normally rests (wheel, gear lever,
  lap). Wait about 3 seconds before the next one.
- **Don't be perfect.** Vary speed, distance and angle a little.
- **Which hand:** this is a right-hand-drive car, so the **driver uses the left hand**
  and the **passenger uses the right hand**.
- **Directions** ("left / right / up / clockwise") are **as you see them from your
  seat**.
- **The filename is the label.** Use the names below. `_x3` in a name means "I did it 3
  times" (default 5).
- **Next / previous repeat** every 2 s while held. For those clips, hold about 1 s, not
  longer, so each repetition counts once.
- **The camera is exclusive.** Only one program can use it, so the gesture service must
  be stopped while recording (step 3 does this).

## Shot list

**Priority: A, D and G** (the [car session checklist](#car-session-checklist)). Then F,
then B, C and E.

### A. Gestures, driver (left hand), daytime: 8 clips, 5 repetitions each

For held poses: show the pose, **hold it still for about 1 second**, lower your hand, rest
about 3 seconds, repeat.

| File | Do this 5 times | `--duration` |
|---|---|---|
| `open_palm_driver_day_1.mp4` | five fingers up, held | 40 |
| `thumb_up_driver_day_1.mp4` | thumbs up, held | 40 |
| `thumb_right_driver_day_1.mp4` | fist, thumb pointing to your right, held | 40 |
| `thumb_left_driver_day_1.mp4` | fist, thumb pointing to your left, held | 40 |
| `phone_vertical_driver_day_1.mp4` | phone hand (thumb + pinky out) held upright | 40 |
| `phone_horizontal_driver_day_1.mp4` | phone hand held sideways | 40 |
| `circle_cw_driver_day_1.mp4` | index finger only, ~1.5 circles clockwise | 45 |
| `circle_ccw_driver_day_1.mp4` | same, counter-clockwise | 45 |

**Pi**, one line at a time:
```bash
python scripts/record_video.py videos/open_palm_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/thumb_up_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/thumb_right_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/thumb_left_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/phone_vertical_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/phone_horizontal_driver_day_1.mp4 --duration 40 --countdown 5
python scripts/record_video.py videos/circle_cw_driver_day_1.mp4 --duration 45 --countdown 5
python scripts/record_video.py videos/circle_ccw_driver_day_1.mp4 --duration 45 --countdown 5
```

### B. Gestures, passenger (right hand), daytime

The same 8, named `..._passenger_day_1.mp4`.

### C. Gestures, driver, at night (dash lights only)

The same 8, named `..._driver_night_1.mp4`.

### D. Look-alikes, nothing should fire: 9 clips, about 60 s each

| File | Do this, repeatedly and naturally |
|---|---|
| `none_gearknob_1.mp4` | grip the gear knob, hold, shift, release |
| `none_pointing_1.mp4` | point at things, point while talking, move the pointing finger around |
| `none_openhand_1.mp4` | wave, reach for the sun visor, open hand near the camera |
| `none_vsign_1.mp4` | V sign, counting 1-2-3 on your fingers, moving them around |
| `none_thanks_1.mp4` | the quick raised hand / thumbs up you give other drivers, like you normally do it |
| `none_phone_1.mp4` | pick up the phone, hold it, scroll, put it down |
| `none_cabin_1.mp4` | drink, use the cup holder, scratch your face, adjust the mirror |
| `none_controls_1.mp4` | AC / radio knobs, seat belt, fingers tapping in the gesture area |
| `none_passenger_talk_1.mp4` | passenger talking with their hands (skip it if you're alone) |

**Pi**, one line at a time:
```bash
python scripts/record_video.py videos/none_gearknob_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_pointing_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_openhand_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_vsign_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_thanks_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_phone_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_cabin_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_controls_1.mp4 --duration 60 --countdown 5
python scripts/record_video.py videos/none_passenger_talk_1.mp4 --duration 60 --countdown 5
```

### E. Random, nothing should fire: 2–3 clips of about 2 minutes

`none_random_1.mp4`, `none_random_2.mp4`: anything at all, both hands. Use
`--duration 120`.

### F. Mixed realistic takes: 2–3 takes of 3–5 minutes

`mixed_driver_day_1.mp4`, with `--duration 240`. Move normally (like G, below) and throw
in about 8–10 gestures. Afterwards, create **`videos/mixed_driver_day_1.txt`** next to
the video, one line per gesture with the approximate time:

```
0:12 thumb_right
0:40 circle_cw
1:05 open_palm
```

±2 seconds is fine. The easiest way: watch the video on the laptop after copying it,
pause at each gesture and note the time.

### G. Real driving, no gestures: 20+ minutes in total, day and (later) night

```bash
python scripts/record_video.py videos/drive_day_1.mp4 --split 300 --duration 1500 --countdown 5
```

Start it while parked, then drive normally. It saves a new file every 5 minutes
(`drive_day_1_part01.mp4`, `_part02`, ...) and stops by itself after 25 minutes
(`--duration 1500`). To stop earlier, press Ctrl+C after you park. Run it inside tmux
(checklist step 3), so it keeps recording if the laptop disconnects.

## Check your recordings

After copying `videos/` to the laptop (checklist step 8, or [SETUP.md](SETUP.md) step
12). **Laptop:**

```powershell
python scripts/evaluate_videos.py --config config/car.yaml --fps 9              # per-clip result + summary
python scripts/evaluate_videos.py --config config/car.yaml --fps 9 --timeline   # every detection with its time
```

`--fps 9` replays the clips at the Pi's real speed.

Each clip line reads `OK` or `FAIL`, with what was detected, the times of any false
triggers, and the share of frames that had a hand in view. A clip where the hand is
seen in only a small share of frames points at a camera aim or lighting problem, not the
gesture rules.

# Recording test videos

These videos are **not training data**: the gestures are geometry rules, not a trained
model. They're used to:

- **tune thresholds** against your real camera, mount, lighting and hands;
- **measure accidental triggers** in normal driving, which matters most for safety;
- **become regression tests:** once a clip behaves correctly, `--export-samples` turns
  it into a small landmark file in `samples/` that `pytest` checks on every run.

Videos stay in `videos/` (gitignored, never pushed).

## Before you record

- **Fix the camera in its final mount.** Don't move it between clips. If you do move
  it, mention it.
- **Gesture clips: park the car.** Never test gestures while driving. Only the `drive_`
  takes are recorded while driving, and in those you don't do any gestures.
- **Between repetitions,** put your hand back where it normally rests (wheel, gear lever,
  lap). Wait about 3 seconds before the next one.
- **Don't be perfect.** Vary speed, distance and angle a little.
- **Which hand:** this is a right-hand-drive car, so the **driver uses the left hand**
  and the **passenger uses the right hand**.
- **The filename is the label.** Use the names below. `_x3` means "I did it 3 times"
  (default 5).
- **One command per clip**, after `cd ~/hand-gesture-control && source .venv/bin/activate`:
  `python scripts/record_video.py videos/<name>.mp4 --duration <seconds>`

## Shot list

**Priority if time is short: A, D and G first** (about 40 minutes including a drive),
then F, then B, C and E.

### A. Gestures, driver (left hand), daytime: 8 clips, 5 repetitions each

| File | Do this 5 times | `--duration` |
|---|---|---|
| `circle_cw_driver_day_1.mp4` | index finger only, ~1.5 circles clockwise | 45 |
| `circle_ccw_driver_day_1.mp4` | same, counter-clockwise | 45 |
| `fist_to_open_driver_day_1.mp4` | hold fist still ~0.5 s, open to five fingers | 40 |
| `open_to_fist_driver_day_1.mp4` | hold five fingers still ~0.5 s, close to fist | 40 |
| `swipe_left_driver_day_1.mp4` | hold V (index + middle) still ~0.5 s, swipe left | 40 |
| `swipe_right_driver_day_1.mp4` | same, swipe right | 40 |
| `swipe_up_driver_day_1.mp4` | same, swipe up | 40 |
| `swipe_down_driver_day_1.mp4` | same, swipe down | 40 |

"Left / right / up / down / clockwise" are **as you see it from the driver's seat**.

### B. Gestures, passenger (right hand), daytime: the same 8, named `..._passenger_day_1.mp4`

### C. Gestures, driver, at night (dash lights only): the same 8, named `..._driver_night_1.mp4`

### D. Look-alikes, nothing should fire: 8 clips, about 60 s each

| File | Do this, repeatedly and naturally |
|---|---|
| `none_gearknob_1.mp4` | grip the gear knob, hold, shift, release |
| `none_pointing_1.mp4` | point at things, point while talking, move the pointing finger around |
| `none_openhand_1.mp4` | wave, reach for the sun visor, open hand near the camera |
| `none_vsign_1.mp4` | V sign, counting 1-2-3 on your fingers, moving them around |
| `none_phone_1.mp4` | pick up the phone, hold it, scroll, put it down |
| `none_cabin_1.mp4` | drink, use the cup holder, scratch your face, adjust the mirror |
| `none_controls_1.mp4` | AC / radio knobs, seat belt, fingers tapping in the gesture area |
| `none_passenger_talk_1.mp4` | passenger talking with their hands |

### E. Random, nothing should fire: 2–3 clips of about 2 minutes

`none_random_1.mp4`, `none_random_2.mp4`: anything at all, both hands. Use
`--duration 120`.

### F. Mixed realistic takes: 2–3 takes of 3–5 minutes

`mixed_driver_day_1.mp4`, with `--duration 240`. Move normally (like H, below) and throw
in about 8–10 gestures. Afterwards, create **`videos/mixed_driver_day_1.txt`** next to
the video, one line per gesture with the approximate time:

```
0:12 swipe_right
0:40 circle_cw
1:05 fist_to_open
```

±2 seconds is fine. The easiest way: watch the video on the laptop after copying it,
pause at each gesture and note the time.

### G. Real driving, no gestures: 20+ minutes in total, day and (later) night

```bash
python scripts/record_video.py videos/drive_day_1.mp4 --split 300
```

Leave it running while you drive normally. It saves a new file every 5 minutes
(`drive_day_1_part01.mp4`, `_part02`, ...). Stop with Ctrl+C when you park.

## Check your recordings

After copying `videos/` to the laptop (see [SETUP.md](SETUP.md) step 7):

```powershell
python scripts/evaluate_videos.py --fps <Pi FPS>              # per-clip result + summary
python scripts/evaluate_videos.py --fps <Pi FPS> --timeline   # every detection with its time
```

Each clip line reads `OK` or `FAIL`, with what was detected, the times of any false
triggers, and the share of frames that had a hand in view. A clip where the hand is
seen in only a small share of frames points at a camera aim or lighting problem, not the
gesture rules.

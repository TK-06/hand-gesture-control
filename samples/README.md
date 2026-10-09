# Recorded samples

One folder per label (`circle_cw/`, `fist_to_open/`, ..., `none/`), one JSON file per take.
Files hold hand-landmark coordinates only, no camera images.

- Record: `python scripts/record_samples.py --label <label>`
- Check / tune: `python scripts/replay_samples.py`
- `pytest` replays every file here and fails if a sample misbehaves.

`none/` takes are normal movements that must fire nothing (reaching, gripping the gear
knob, steering, scratching, waving). They are the accidental-trigger regression tests.

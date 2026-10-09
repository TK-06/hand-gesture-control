"""Every recording under samples/ must behave as labelled with the default config.

Record samples with scripts/record_samples.py; this test picks them up automatically.
"""

import pytest

from gesturectl.config import load_config
from gesturectl.recording import check, load, replay, sample_files

FILES = sample_files()


@pytest.mark.skipif(not FILES, reason="no recorded samples yet (run scripts/record_samples.py)")
@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_recorded_sample(path):
    rec = load(path)
    fired = [e.gesture for e in replay(rec, load_config())]
    ok, why = check(rec.label, fired)
    assert ok, f"{path.name}: {why}"

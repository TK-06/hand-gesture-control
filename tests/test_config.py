import pytest

from gesturectl.config import AppConfig, ConfigError, from_dict, load_config


def test_default_yaml_matches_code_defaults():
    assert load_config() == AppConfig()


def test_unknown_key_is_an_error():
    with pytest.raises(ConfigError, match="unknown key"):
        from_dict({"camera": {"widht": 640}})


def test_wrong_type_is_an_error():
    with pytest.raises(ConfigError, match="expected an integer"):
        from_dict({"camera": {"width": "640"}})


def test_unknown_action_is_an_error():
    with pytest.raises(ConfigError, match="unknown action"):
        from_dict({"mapping": {"circle_cw": "louder"}})


def test_unknown_gesture_is_an_error():
    with pytest.raises(ConfigError, match="unknown gesture"):
        from_dict({"mapping": {"thumbs_up": "play"}})


def test_mapping_replaces_the_default_and_null_disables():
    cfg = from_dict({"mapping": {"circle_cw": "volume_up", "circle_ccw": None}})
    assert cfg.mapping == {"circle_cw": "volume_up", "circle_ccw": None}


def test_nested_values_are_applied():
    cfg = from_dict({"gestures": {"circle": {"step_deg": 90}}, "gating": {"active_zone": [0.1, 0.2, 0.9, 1.0]}})
    assert cfg.gestures.circle.step_deg == 90.0
    assert cfg.gating.active_zone == (0.1, 0.2, 0.9, 1.0)


@pytest.mark.parametrize(
    "data",
    [
        {"gating": {"active_zone": [0.5, 0.0, 0.4, 1.0]}},
        {"camera": {"rotate": 45}},
        {"camera": {"source": "gopro"}},
        {"tracker": {"num_hands": 0}},
    ],
)
def test_invalid_values_are_errors(data):
    with pytest.raises(ConfigError):
        from_dict(data)

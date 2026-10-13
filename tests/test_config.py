import dataclasses
import textwrap

import pytest

import gesturectl.config as config_module
from gesturectl.config import DEFAULT_CONFIG, PROJECT_ROOT, AppConfig, ConfigError, from_dict, load_config


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


# ---------------------------------------------------------------- layered configs


def _write(path, text):
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


@pytest.fixture
def tuned_default(tmp_path, monkeypatch):
    """A stand-in default.yaml whose values differ from the code defaults, as after tuning."""
    path = _write(
        tmp_path / "default.yaml",
        """
        camera: {rotate: 0, fps: 25}
        gestures:
          circle: {step_deg: 120.0, first_step_deg: 300.0}
        mapping: {circle_cw: volume_up, circle_ccw: volume_down}
        """,
    )
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG", path)
    return path


def test_override_file_is_layered_on_top_of_default_yaml(tmp_path, tuned_default):
    car = _write(
        tmp_path / "car.yaml",
        """
        camera: {rotate: 180}
        gestures:
          circle: {step_deg: 90}
        """,
    )
    cfg = load_config(car)
    assert cfg.camera.rotate == 180  # from car.yaml
    assert cfg.camera.fps == 25  # from default.yaml
    assert cfg.gestures.circle.step_deg == 90.0  # car.yaml wins
    assert cfg.gestures.circle.first_step_deg == 300.0  # tuned default.yaml value, not the code default
    assert cfg.mapping == {"circle_cw": "volume_up", "circle_ccw": "volume_down"}


def test_override_mapping_replaces_the_whole_mapping(tmp_path, tuned_default):
    car = _write(tmp_path / "car.yaml", "mapping: {circle_cw: next}\n")
    assert load_config(car).mapping == {"circle_cw": "next"}


def test_override_with_a_typo_is_still_an_error(tmp_path, tuned_default):
    car = _write(tmp_path / "car.yaml", "camera: {rotaet: 180}\n")
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(car)


def test_loading_default_explicitly_is_the_same_as_no_path():
    assert load_config(DEFAULT_CONFIG) == load_config()


def test_car_yaml_rotates_the_camera_and_sends_to_bluetooth_only():
    car = load_config(PROJECT_ROOT / "config" / "car.yaml")
    default = load_config()
    assert car.camera.rotate == 180
    assert car.actions.backend == "bt_hid"
    restored = dataclasses.replace(
        car,
        camera=dataclasses.replace(car.camera, rotate=0),
        actions=dataclasses.replace(car.actions, backend="print"),
    )
    assert restored == default


def test_repeat_gestures_must_be_known():
    with pytest.raises(ConfigError, match="repeat_gestures"):
        from_dict({"gestures": {"static": {"repeat_gestures": ["thumb_sideways"]}}})


def test_repeat_gestures_list_is_loaded():
    cfg = from_dict({"gestures": {"static": {"repeat_gestures": ["thumb_up"], "repeat_s": 1.5}}})
    assert cfg.gestures.static.repeat_gestures == ["thumb_up"] and cfg.gestures.static.repeat_s == 1.5

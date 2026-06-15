"""Settings.load: built-in defaults, settings.json values, env overrides, validation."""

import json
from pathlib import Path

import pytest

from data_simulator.config import ConfigError, Settings

MISSING = Path("/nonexistent/settings.json")


def _write_settings(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_builtin_defaults_without_settings_file():
    settings = Settings.load(settings_path=MISSING, env={})
    assert settings.data_root == Path("/data")
    assert settings.seed_dir == Path("/data/seed")
    assert settings.state_file == Path("/data/sim_state/state.json")
    assert settings.port == 6030
    assert settings.link_mode == "hardlink"
    assert settings.glm.interval_minutes == 10
    assert settings.radar.retention_minutes == 180
    assert settings.radar.retention_ticks == 24
    assert settings.wrf.interval_minutes == 360
    assert settings.wrf.retention_ticks == 5
    assert settings.glm_accum_minutes == 10
    assert settings.wrf_expected_hours == 72
    assert settings.radar_subvolume_offsets == {"01": 0, "02": 20, "04": 40}


def test_seed_dirs_default_under_seed_root():
    settings = Settings.load(settings_path=MISSING, env={})
    assert settings.glm_seed_dir == Path("/data/seed/glm_h5")
    assert settings.radar_seed_dir == Path("/data/seed/radar_h5")
    assert settings.wrf_seed_dir == Path("/data/seed/wrf_nc")


def test_seed_dirs_follow_sim_seed_dir_base():
    settings = Settings.load(settings_path=MISSING, env={"SIM_SEED_DIR": "/master"})
    assert settings.glm_seed_dir == Path("/master/glm_h5")
    assert settings.radar_seed_dir == Path("/master/radar_h5")
    assert settings.wrf_seed_dir == Path("/master/wrf_nc")


def test_per_source_seed_dirs_override_independently():
    settings = Settings.load(
        settings_path=MISSING,
        env={
            "SIM_GLM_SEED_DIR": "/home/u/raw/glm_raw_data/glm_h5",
            "SIM_RADAR_SEED_DIR": "/home/u/raw/radar_h5",
            "SIM_WRF_SEED_DIR": "/home/u/raw/wrf_raw_data/wrf_nc",
        },
    )
    assert settings.glm_seed_dir == Path("/home/u/raw/glm_raw_data/glm_h5")
    assert settings.radar_seed_dir == Path("/home/u/raw/radar_h5")
    assert settings.wrf_seed_dir == Path("/home/u/raw/wrf_raw_data/wrf_nc")
    # An explicit per-source override wins over the SIM_SEED_DIR base.
    mixed = Settings.load(
        settings_path=MISSING,
        env={"SIM_SEED_DIR": "/master", "SIM_RADAR_SEED_DIR": "/elsewhere/radar"},
    )
    assert mixed.glm_seed_dir == Path("/master/glm_h5")
    assert mixed.radar_seed_dir == Path("/elsewhere/radar")


def test_repo_settings_json_is_valid():
    settings = Settings.load(env={})  # default path = repo settings.json
    assert settings.glm.enabled is True
    assert settings.wrf.retention_minutes == 1080
    assert settings.wrf.retention_ticks == 5


def test_settings_json_values_used(tmp_path):
    path = _write_settings(
        tmp_path,
        {
            "link_mode": "copy",
            "glm": {"enabled": False, "interval_minutes": 5, "accum_minutes": 6},
            "radar": {"subvolume_offsets_seconds": {"01": 0, "02": 30}},
            "wrf": {"retention_minutes": 720, "expected_forecast_hours": 48},
        },
    )
    settings = Settings.load(settings_path=path, env={})
    assert settings.link_mode == "copy"
    assert settings.glm.enabled is False
    assert settings.glm.interval_minutes == 5
    assert settings.glm_accum_minutes == 6
    assert settings.radar_subvolume_offsets == {"01": 0, "02": 30}
    assert settings.wrf.retention_minutes == 720
    assert settings.wrf_expected_hours == 48
    # Untouched keys keep defaults
    assert settings.radar.interval_minutes == 10


def test_env_overrides_settings_json(tmp_path):
    path = _write_settings(
        tmp_path, {"link_mode": "copy", "glm": {"interval_minutes": 5}}
    )
    settings = Settings.load(
        settings_path=path,
        env={
            "SIM_LINK_MODE": "hardlink",
            "SIM_GLM_INTERVAL_MINUTES": "15",
            "SIM_GLM_ENABLED": "false",
            "SIM_WRF_EXPECTED_HOURS": "24",
            "SIM_DATA_ROOT": "/srv/data",
        },
    )
    assert settings.link_mode == "hardlink"
    assert settings.glm.interval_minutes == 15
    assert settings.glm.enabled is False
    assert settings.wrf_expected_hours == 24
    assert settings.data_root == Path("/srv/data")
    assert settings.seed_dir == Path("/srv/data/seed")


def test_settings_path_from_env(tmp_path):
    path = _write_settings(tmp_path, {"glm": {"interval_minutes": 7}})
    settings = Settings.load(env={"SIM_SETTINGS_PATH": str(path)})
    assert settings.glm.interval_minutes == 7


def test_invalid_link_mode_rejected():
    with pytest.raises(ConfigError):
        Settings.load(settings_path=MISSING, env={"SIM_LINK_MODE": "symlink"})


def test_invalid_interval_rejected():
    with pytest.raises(ConfigError):
        Settings.load(settings_path=MISSING, env={"SIM_GLM_INTERVAL_MINUTES": "0"})


def test_invalid_port_rejected():
    with pytest.raises(ConfigError):
        Settings.load(settings_path=MISSING, env={"SIM_PORT": "99999"})


def test_invalid_accum_minutes_rejected(tmp_path):
    path = _write_settings(tmp_path, {"glm": {"accum_minutes": 0}})
    with pytest.raises(ConfigError):
        Settings.load(settings_path=path, env={})


def test_retention_ticks_env_override():
    settings = Settings.load(settings_path=MISSING, env={"SIM_WRF_RETENTION_TICKS": "8"})
    assert settings.wrf.retention_ticks == 8


def test_invalid_retention_ticks_rejected():
    with pytest.raises(ConfigError):
        Settings.load(settings_path=MISSING, env={"SIM_WRF_RETENTION_TICKS": "0"})

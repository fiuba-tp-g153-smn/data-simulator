"""Settings.from_env: defaults, overrides, fail-fast validation."""

from pathlib import Path

import pytest

from feed_simulator.config import ConfigError, Settings


def test_defaults():
    settings = Settings.from_env(env={})
    assert settings.data_root == Path("/data")
    assert settings.seed_dir == Path("/data/seed")
    assert settings.state_file == Path("/data/sim_state/state.json")
    assert settings.port == 6030
    assert settings.link_mode == "hardlink"
    assert settings.glm.interval_minutes == 10
    assert settings.radar.retention_minutes == 180
    assert settings.wrf.interval_minutes == 360
    assert settings.wrf.retention_minutes == 1080


def test_overrides():
    settings = Settings.from_env(
        env={
            "SIM_DATA_ROOT": "/srv/data",
            "SIM_PORT": "7000",
            "SIM_LINK_MODE": "copy",
            "SIM_GLM_ENABLED": "false",
            "SIM_RADAR_INTERVAL_MINUTES": "5",
        }
    )
    assert settings.data_root == Path("/srv/data")
    assert settings.seed_dir == Path("/srv/data/seed")
    assert settings.port == 7000
    assert settings.link_mode == "copy"
    assert settings.glm.enabled is False
    assert settings.radar.interval_minutes == 5


def test_invalid_link_mode_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env(env={"SIM_LINK_MODE": "symlink"})


def test_invalid_interval_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env(env={"SIM_GLM_INTERVAL_MINUTES": "0"})


def test_invalid_port_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env(env={"SIM_PORT": "99999"})

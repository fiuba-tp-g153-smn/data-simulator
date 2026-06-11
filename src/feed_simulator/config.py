"""Environment-driven settings for the feed simulator."""

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when the environment configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SourceSettings:
    """Per-source replay settings."""

    enabled: bool
    interval_minutes: int
    retention_minutes: int


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable simulator configuration resolved from environment variables."""

    data_root: Path
    seed_dir: Path
    state_file: Path
    port: int
    link_mode: str
    glm: SourceSettings
    radar: SourceSettings
    wrf: SourceSettings

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ) if env is None else env
        data_root = Path(env.get("SIM_DATA_ROOT", "/data"))
        settings = cls(
            data_root=data_root,
            seed_dir=Path(env.get("SIM_SEED_DIR", str(data_root / "seed"))),
            state_file=Path(
                env.get("SIM_STATE_FILE", str(data_root / "sim_state/state.json"))
            ),
            port=int(env.get("SIM_PORT", "6030")),
            link_mode=env.get("SIM_LINK_MODE", "hardlink"),
            glm=_source_settings(env, "GLM", interval=10, retention=180),
            radar=_source_settings(env, "RADAR", interval=10, retention=180),
            wrf=_source_settings(env, "WRF", interval=360, retention=1080),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.link_mode not in ("hardlink", "copy"):
            raise ConfigError(f"SIM_LINK_MODE must be hardlink|copy, got {self.link_mode}")
        if not 0 < self.port < 65536:
            raise ConfigError(f"SIM_PORT out of range: {self.port}")
        for name, source in (("GLM", self.glm), ("RADAR", self.radar), ("WRF", self.wrf)):
            if source.interval_minutes <= 0:
                raise ConfigError(f"SIM_{name}_INTERVAL_MINUTES must be > 0")
            if source.retention_minutes <= 0:
                raise ConfigError(f"SIM_{name}_RETENTION_MINUTES must be > 0")


def _source_settings(
    env: dict[str, str], name: str, interval: int, retention: int
) -> SourceSettings:
    return SourceSettings(
        enabled=env.get(f"SIM_{name}_ENABLED", "true").lower() == "true",
        interval_minutes=int(env.get(f"SIM_{name}_INTERVAL_MINUTES", str(interval))),
        retention_minutes=int(env.get(f"SIM_{name}_RETENTION_MINUTES", str(retention))),
    )

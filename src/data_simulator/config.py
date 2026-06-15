"""Simulator configuration: settings.json defaults, overridable via env vars.

Same scheme as tiles-processor: tunables live in settings.json; every scalar
can be overridden with a SIM_* environment variable (env > settings.json >
built-in default). Deployment-level values (paths, port) are env-only.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS_PATH = Path(__file__).parents[2] / "settings.json"

_SOURCE_DEFAULTS = {
    "glm": {"interval_minutes": 10, "retention_minutes": 180, "retention_ticks": 24},
    "radar": {"interval_minutes": 10, "retention_minutes": 180, "retention_ticks": 24},
    "wrf": {"interval_minutes": 360, "retention_minutes": 1080, "retention_ticks": 5},
}
_DEFAULT_GLM_ACCUM_MINUTES = 10
_DEFAULT_WRF_EXPECTED_HOURS = 72
_DEFAULT_SUBVOLUME_OFFSETS = {"01": 0, "02": 20, "04": 40}


class ConfigError(ValueError):
    """Raised when the configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SourceSettings:
    """Per-source replay settings."""

    enabled: bool
    interval_minutes: int
    retention_minutes: int  # min-age floor: data younger than this is always kept
    retention_ticks: int  # ring size: the newest N ticks are always kept


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable simulator configuration (settings.json + env overrides)."""

    data_root: Path
    seed_dir: Path
    glm_seed_dir: Path
    radar_seed_dir: Path
    wrf_seed_dir: Path
    state_file: Path
    port: int
    link_mode: str
    glm: SourceSettings
    radar: SourceSettings
    wrf: SourceSettings
    glm_accum_minutes: int
    wrf_expected_hours: int
    radar_subvolume_offsets: dict[str, int]

    @classmethod
    def load(
        cls, settings_path: Path | None = None, env: dict[str, str] | None = None
    ) -> "Settings":
        env = dict(os.environ) if env is None else env
        raw = _read_settings_file(settings_path, env)
        resolve = _Resolver(raw, env)

        data_root = Path(env.get("SIM_DATA_ROOT", "/data"))
        seed_dir = Path(env.get("SIM_SEED_DIR", str(data_root / "seed")))
        settings = cls(
            data_root=data_root,
            seed_dir=seed_dir,
            glm_seed_dir=_seed_dir(env, "SIM_GLM_SEED_DIR", seed_dir, "glm_h5"),
            radar_seed_dir=_seed_dir(env, "SIM_RADAR_SEED_DIR", seed_dir, "radar_h5"),
            wrf_seed_dir=_seed_dir(env, "SIM_WRF_SEED_DIR", seed_dir, "wrf_nc"),
            state_file=Path(
                env.get("SIM_STATE_FILE", str(data_root / "sim_state/state.json"))
            ),
            port=int(env.get("SIM_PORT", "6030")),
            link_mode=resolve.text((), "link_mode", "SIM_LINK_MODE", "hardlink"),
            glm=resolve.source("glm"),
            radar=resolve.source("radar"),
            wrf=resolve.source("wrf"),
            glm_accum_minutes=resolve.number(
                ("glm",), "accum_minutes", "SIM_GLM_ACCUM_MINUTES",
                _DEFAULT_GLM_ACCUM_MINUTES,
            ),
            wrf_expected_hours=resolve.number(
                ("wrf",), "expected_forecast_hours", "SIM_WRF_EXPECTED_HOURS",
                _DEFAULT_WRF_EXPECTED_HOURS,
            ),
            radar_subvolume_offsets=resolve.offsets(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.link_mode not in ("hardlink", "copy"):
            raise ConfigError(f"link_mode must be hardlink|copy, got {self.link_mode}")
        if not 0 < self.port < 65536:
            raise ConfigError(f"SIM_PORT out of range: {self.port}")
        if self.glm_accum_minutes <= 0:
            raise ConfigError("glm accum_minutes must be > 0")
        if self.wrf_expected_hours <= 0:
            raise ConfigError("wrf expected_forecast_hours must be > 0")
        for name, source in (("glm", self.glm), ("radar", self.radar), ("wrf", self.wrf)):
            if source.interval_minutes <= 0:
                raise ConfigError(f"{name} interval_minutes must be > 0")
            if source.retention_minutes <= 0:
                raise ConfigError(f"{name} retention_minutes must be > 0")
            if source.retention_ticks <= 0:
                raise ConfigError(f"{name} retention_ticks must be > 0")


class _Resolver:
    """Resolves one value as env override > settings.json > default."""

    def __init__(self, raw: dict, env: dict[str, str]) -> None:
        self._raw = raw
        self._env = env

    def source(self, name: str) -> SourceSettings:
        defaults = _SOURCE_DEFAULTS[name]
        prefix = f"SIM_{name.upper()}"
        return SourceSettings(
            enabled=self.flag((name,), "enabled", f"{prefix}_ENABLED", True),
            interval_minutes=self.number(
                (name,), "interval_minutes", f"{prefix}_INTERVAL_MINUTES",
                defaults["interval_minutes"],
            ),
            retention_minutes=self.number(
                (name,), "retention_minutes", f"{prefix}_RETENTION_MINUTES",
                defaults["retention_minutes"],
            ),
            retention_ticks=self.number(
                (name,), "retention_ticks", f"{prefix}_RETENTION_TICKS",
                defaults["retention_ticks"],
            ),
        )

    def text(self, section: tuple, key: str, env_name: str, default: str) -> str:
        if env_name in self._env:
            return self._env[env_name]
        return str(self._from_json(section, key, default))

    def number(self, section: tuple, key: str, env_name: str, default: int) -> int:
        if env_name in self._env:
            return int(self._env[env_name])
        return int(self._from_json(section, key, default))

    def flag(self, section: tuple, key: str, env_name: str, default: bool) -> bool:
        if env_name in self._env:
            return self._env[env_name].lower() == "true"
        return bool(self._from_json(section, key, default))

    def offsets(self) -> dict[str, int]:
        raw = self._from_json(("radar",), "subvolume_offsets_seconds", None)
        if raw is None:
            return dict(_DEFAULT_SUBVOLUME_OFFSETS)
        return {str(subvol): int(seconds) for subvol, seconds in raw.items()}

    def _from_json(self, section: tuple, key: str, default):
        node = self._raw
        for part in section:
            node = node.get(part, {})
        value = node.get(key)
        return default if value is None else value


def _seed_dir(env: dict[str, str], var: str, seed_dir: Path, subdir: str) -> Path:
    """Per-source seed dir: env override, else the ``<seed_dir>/<subdir>`` default."""
    return Path(env.get(var, str(seed_dir / subdir)))


def _read_settings_file(settings_path: Path | None, env: dict[str, str]) -> dict:
    if settings_path is None:
        settings_path = Path(env.get("SIM_SETTINGS_PATH", str(_DEFAULT_SETTINGS_PATH)))
    if not settings_path.exists():
        logger.warning("settings.json not found at %s; using defaults", settings_path)
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))

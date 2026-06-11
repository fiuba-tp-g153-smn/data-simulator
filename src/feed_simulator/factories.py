"""Composition root: wire settings into replayers, scheduler and the API app."""

import logging
from pathlib import Path

from fastapi import FastAPI

from feed_simulator.api.app import create_app
from feed_simulator.clock import Clock, SystemClock
from feed_simulator.config import Settings, SourceSettings
from feed_simulator.core.emitter import FileEmitter
from feed_simulator.core.pruner import Pruner
from feed_simulator.core.replayer import Replayer
from feed_simulator.core.scheduler import ScheduledSource, TickScheduler
from feed_simulator.sources.glm.glm_attr_rewriter import GlmAttrRewriter
from feed_simulator.sources.glm.glm_replayer import GlmReplayer
from feed_simulator.sources.radar.radar_replayer import RadarReplayer
from feed_simulator.sources.wrf.wrf_replayer import WrfReplayer
from feed_simulator.state.state_store import JsonStateStore

logger = logging.getLogger(__name__)


def create_application(settings: Settings) -> FastAPI:
    clock = SystemClock()
    state_store = JsonStateStore(settings.state_file)
    scheduler = create_scheduler(settings, state_store, clock)
    return create_app(scheduler, state_store, settings, clock)


def create_scheduler(
    settings: Settings, state_store: JsonStateStore, clock: Clock
) -> TickScheduler:
    emitter = FileEmitter(settings.link_mode)
    sources: dict[str, ScheduledSource] = {}
    for source_settings, replayer, dest_dir in _enabled_sources(settings, emitter):
        replayer.discover_seed()
        sources[replayer.source_id] = ScheduledSource(
            replayer=replayer,
            interval_minutes=source_settings.interval_minutes,
            pruner=Pruner((dest_dir,), source_settings.retention_minutes),
        )
    if not sources:
        raise ValueError("No sources enabled — nothing to simulate")
    return TickScheduler(sources, state_store, clock)


def _enabled_sources(
    settings: Settings, emitter: FileEmitter
) -> list[tuple[SourceSettings, Replayer, Path]]:
    sources: list[tuple[SourceSettings, Replayer, Path]] = []
    if settings.glm.enabled:
        dest = settings.data_root / "glm_h5"
        replayer = GlmReplayer(
            seed_dir=settings.seed_dir / "glm_h5",
            dest_dir=dest,
            emitter=emitter,
            attr_rewriter=GlmAttrRewriter(),
        )
        sources.append((settings.glm, replayer, dest))
    if settings.radar.enabled:
        dest = settings.data_root / "radar_h5"
        replayer = RadarReplayer(
            seed_dir=settings.seed_dir / "radar_h5", dest_dir=dest, emitter=emitter
        )
        sources.append((settings.radar, replayer, dest))
    if settings.wrf.enabled:
        dest = settings.data_root / "wrf_nc"
        replayer = WrfReplayer(
            seed_dir=settings.seed_dir / "wrf_nc", dest_dir=dest, emitter=emitter
        )
        sources.append((settings.wrf, replayer, dest))
    return sources

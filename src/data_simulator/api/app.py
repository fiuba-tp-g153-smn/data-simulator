"""FastAPI app factory: /health, /status, /tick/{source}."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from data_simulator.api.schemas import (
    CursorInfo,
    SourceStatus,
    StatusResponse,
    TickResponse,
)
from data_simulator.clock import Clock
from data_simulator.config import Settings
from data_simulator.core.scheduler import TickScheduler
from data_simulator.core.tick_alignment import next_aligned
from data_simulator.state.models import SourceState
from data_simulator.state.state_store import JsonStateStore


def create_app(
    scheduler: TickScheduler,
    state_store: JsonStateStore,
    settings: Settings,
    clock: Clock,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        scheduler.start()
        yield
        await scheduler.stop()

    app = FastAPI(title="data-simulator", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        sim_state = state_store.load()
        sources = {
            source_id: _source_status(
                sim_state.for_source(source_id), scheduler, settings, source_id, clock
            )
            for source_id in scheduler.source_ids
        }
        return StatusResponse(sources=sources)

    @app.post("/tick/{source_id}", response_model=TickResponse)
    async def force_tick(source_id: str) -> TickResponse:
        try:
            triggered = await scheduler.force_tick(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown source {source_id}") from exc
        if not triggered:
            raise HTTPException(status_code=409, detail=f"{source_id} tick already running")
        return TickResponse(source=source_id, triggered=True)

    return app


def _source_status(
    state: SourceState,
    scheduler: TickScheduler,
    settings: Settings,
    source_id: str,
    clock: Clock,
) -> SourceStatus:
    interval = scheduler.interval_minutes(source_id)
    source_settings = getattr(settings, source_id)
    retention = source_settings.retention_minutes
    return SourceStatus(
        enabled=True,
        interval_minutes=interval,
        last_tick=state.last_tick,
        next_tick=next_aligned(clock.now(), interval),
        cursors={
            key: CursorInfo(index=c.index, direction=c.direction)
            for key, c in state.cursors.items()
        },
        emitted_total=state.emitted_total,
        ledger_size=len(state.ledger),
        retention_minutes=retention,
        retention_ticks=source_settings.retention_ticks,
        last_error=state.last_error,
    )

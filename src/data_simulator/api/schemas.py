"""Pydantic response models for the status API."""

from datetime import datetime

from pydantic import BaseModel


class CursorInfo(BaseModel):
    index: int
    direction: int


class SourceStatus(BaseModel):
    enabled: bool
    interval_minutes: int
    last_tick: datetime | None
    next_tick: datetime | None
    cursors: dict[str, CursorInfo]
    emitted_total: int
    ledger_size: int
    retention_minutes: int
    retention_ticks: int
    last_error: str | None


class StatusResponse(BaseModel):
    sources: dict[str, SourceStatus]


class TickResponse(BaseModel):
    source: str
    triggered: bool

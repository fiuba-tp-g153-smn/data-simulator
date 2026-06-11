"""GlmReplayer: window chunking, tick planning, backward reversal."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from data_simulator.core.emitter import FileEmitter
from data_simulator.sources.glm.glm_attr_rewriter import GlmAttrRewriter
from data_simulator.sources.glm.glm_filenames import (
    GlmFilenameParts,
    build_glm_filename,
    parse_glm_filename,
)
from data_simulator.sources.glm.glm_replayer import GlmReplayer
from data_simulator.state.models import SourceState

SEED_START = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)
TICK = datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc)


def _make_seed(seed_dir: Path, minutes: int) -> list[str]:
    seed_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(minutes):
        start = SEED_START + timedelta(minutes=i)
        name = build_glm_filename(
            GlmFilenameParts(
                mode="M3", platform="G19", start=start, end=start + timedelta(minutes=1)
            )
        )
        (seed_dir / name).touch()
        names.append(name)
    return names


def _replayer(tmp_path: Path, minutes: int = 20) -> GlmReplayer:
    seed_dir = tmp_path / "seed"
    _make_seed(seed_dir, minutes)
    replayer = GlmReplayer(
        seed_dir=seed_dir,
        dest_dir=tmp_path / "out",
        emitter=FileEmitter("copy"),
        attr_rewriter=GlmAttrRewriter(),
    )
    replayer.discover_seed()
    return replayer


def test_seed_chunked_into_windows(tmp_path):
    assert _replayer(tmp_path, minutes=20).window_count == 2


def test_partial_trailing_window_dropped(tmp_path):
    assert _replayer(tmp_path, minutes=25).window_count == 2


def test_empty_seed_rejected(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    replayer = GlmReplayer(
        seed_dir=seed_dir,
        dest_dir=tmp_path / "out",
        emitter=FileEmitter("copy"),
        attr_rewriter=GlmAttrRewriter(),
    )
    with pytest.raises(ValueError):
        replayer.discover_seed()


def test_plan_maps_window_to_tick_minutes(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())

    assert len(plan.mappings) == 10
    first = parse_glm_filename(plan.mappings[0].dst.name)
    last = parse_glm_filename(plan.mappings[-1].dst.name)
    assert first.start == TICK - timedelta(minutes=10)
    assert last.end == TICK
    assert plan.mappings[0].coverage_start == first.start
    assert plan.mappings[0].coverage_end == first.end


def test_plan_advances_cursor_and_ledger(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    state = plan.next_state
    assert state.last_tick == TICK
    assert state.emitted_total == 10
    assert len(state.ledger) == 10
    assert state.cursors["default"].index == 1


def test_backward_direction_reverses_file_order(tmp_path):
    replayer = _replayer(tmp_path, minutes=20)  # 2 windows: 0(fwd), 1(fwd), 0(bwd), ...
    state = SourceState()
    plans = []
    for i in range(3):
        plan = replayer.plan_tick(TICK + i * timedelta(minutes=10), state)
        plans.append(plan)
        state = plan.next_state

    forward_srcs = [m.src.name for m in plans[0].mappings]
    peak_srcs = [m.src.name for m in plans[1].mappings]
    backward_srcs = [m.src.name for m in plans[2].mappings]
    assert forward_srcs == sorted(forward_srcs)
    assert peak_srcs == sorted(peak_srcs)  # peak window still travels forward
    assert backward_srcs == sorted(forward_srcs, reverse=True)  # window 0 replayed in reverse

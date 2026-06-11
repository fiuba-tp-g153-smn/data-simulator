# data-simulator

Replays the static GLM / SINARAME radar / WRF-ARG4K snapshots of **tiles-processor** as if new data were arriving, so the full pipeline (producer → RabbitMQ → workers → tiles) runs continuously on a VPS without live feeds.

## How it works

The tiles-processor producer identifies images purely by **filename-derived timestamps** (dedup = `image_id` vs existing S3 tiles). The simulator walks the seed snapshot in **ping-pong order** (oldest→newest→oldest, reflecting at the ends so there is never a content jump) and emits files renamed to the current time:

| Source | Cadence (UTC-aligned) | Per tick                                                                                                | Mechanism                                                                                                                                                    |
| ------ | --------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GLM    | every 10 min          | one complete 10-file window mapped to `[T-10min, T)`                                                    | **copy** + rewrite of the `time_coverage_start/end` HDF5 attrs (the worker aggregation bins files by those internal attrs — stale values would fail the job) |
| Radar  | every 10 min          | one scan per (radar, subvolume) series, all variables                                                   | hardlink with rewritten timestamp (+0s/+20s/+40s per subvolume 01/02/04 to keep image_ids unique)                                                            |
| WRF    | 00/06/12/18           | one complete run (F000–F072, FIELD2D **and** FIELD3D = 146 files) with `INIT_TAG` rewritten to the slot | hardlink (a run is ~11.5 GB; links are instant and cost no disk)                                                                                             |

Incomplete WRF runs in the seed are excluded automatically. Emissions older than the retention window are pruned (only files the simulator itself created — tracked in a ledger — are ever deleted). State (cursors, last tick, ledger) persists in `<data>/sim_state/state.json`, so restarts resume where they left off; on startup the most recent aligned tick is emitted immediately (catch-up).

## One-time seed migration

The snapshots must move out of the watched dirs into `seed/` (run with the tiles-processor producer stopped):

```bash
cd ../tiles-processor/data
mkdir -p seed sim_state
mv glm_h5  seed/glm_h5
mv radar_h5 seed/radar_h5
mv wrf_nc  seed/wrf_nc
mkdir -p glm_h5 wrf_nc radar_h5
for d in seed/radar_h5/*/; do mkdir -p "radar_h5/$(basename "$d")"; done
```

The producer keeps watching `data/{glm_h5,radar_h5,wrf_nc}` — no tiles-processor config changes.

## Run

```bash
cp .env.example .env          # set TILES_DATA_DIR to the tiles-processor data dir
docker compose up --build -d
```

The single bind mount must cover both `seed/` and the watched dirs (same filesystem ⇒ hardlinks work). If the data dir is owned by another user, add `user: "${UID}:${GID}"` to the service.

## Configuration

Same scheme as tiles-processor: tunables live in **`settings.json`** (mounted into the container — edit + restart, no rebuild); `.env` holds only deployment values (`TILES_DATA_DIR`, `SIM_PORT`). Every scalar in settings.json can also be overridden with an env var (env > settings.json > built-in default):

| settings.json | env override |
|---|---|
| `link_mode` | `SIM_LINK_MODE` |
| `<src>.enabled` | `SIM_<SRC>_ENABLED` |
| `<src>.interval_minutes` | `SIM_<SRC>_INTERVAL_MINUTES` |
| `<src>.retention_minutes` | `SIM_<SRC>_RETENTION_MINUTES` |
| `glm.accum_minutes` | `SIM_GLM_ACCUM_MINUTES` |
| `wrf.expected_forecast_hours` | `SIM_WRF_EXPECTED_HOURS` |
| `radar.subvolume_offsets_seconds` | — (settings.json only) |

`glm.accum_minutes` must match the producer's GLM window size. Paths are env-only: `SIM_DATA_ROOT`, `SIM_SEED_DIR`, `SIM_STATE_FILE`, `SIM_SETTINGS_PATH`.

## API (port 6030)

- `GET /health` — liveness
- `GET /status` — per source: last/next tick, cursor positions + direction, emitted totals, ledger size, last error
- `POST /tick/{glm|radar|wrf}` — force a tick now (409 if one is running). Radar/WRF can be forced freely; forcing GLM more than once inside the same 10-minute wall-clock window rebuilds the same filenames (overwrite-skip, no new window).

## Notes

- GLM windows become eligible for the producer ~30 s after the tick (its safety lag) and are discovered on its next 5-min scan — up to ~5 min latency is normal.
- At a ping-pong turnaround the weather plays in reverse for one pass; intra-window GLM file order is reversed too so motion stays continuous.
- `SIM_LINK_MODE=copy` exists as an escape hatch should the pipeline ever start mutating its input files in place (hardlinks share inodes with the seed).
- Filename formats are mirrored from `tiles-processor/src/models/{radar_config,wrf_config}.py`, `src/models/glm_folder_config.py`; window semantics from `src/data_sources/glm_folder.py`; attr contract from `src/services/glm_aggregation.py`.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

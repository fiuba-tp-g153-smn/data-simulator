# data-simulator

Replays the static GLM / SINARAME radar / WRF-ARG4K snapshots of **tiles-processor** as if new data were arriving, so the full pipeline (producer → RabbitMQ → workers → tiles) runs continuously on a VPS without live feeds.

## How it works

The tiles-processor producer identifies images purely by **filename-derived timestamps** (dedup = `image_id` vs existing S3 tiles). The simulator walks the seed snapshot in **ping-pong order** (oldest→newest→oldest, reflecting at the ends so there is never a content jump) and emits files renamed to the current time:

| Source | Cadence (UTC-aligned) | Per tick                                                                                                | Mechanism                                                                                                                                                    |
| ------ | --------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GLM    | every 10 min          | one complete 10-file window mapped to `[T-10min, T)`                                                    | **copy** + rewrite of the `time_coverage_start/end` HDF5 attrs (the worker aggregation bins files by those internal attrs — stale values would fail the job) |
| Radar  | every 10 min          | one scan per (radar, subvolume) series, all variables                                                   | hardlink with rewritten timestamp (+0s/+20s/+40s per subvolume 01/02/04 to keep image_ids unique)                                                            |
| WRF    | 00/06/12/18           | one complete run (F000–F072, FIELD2D **and** FIELD3D = 146 files) with `INIT_TAG` rewritten to the slot | hardlink (a run is ~11.5 GB; links are instant and cost no disk)                                                                                             |

Incomplete WRF runs in the seed are excluded automatically. Old emissions are pruned by a hybrid **ring + floor** rule: the newest `retention_ticks` ticks per source are always kept (count-based, so a slow/stopped consumer is never pruned out from under it), and nothing younger than `retention_minutes` (the min-age floor) is ever deleted — an emission is removed only when it is *both* beyond the ring and older than the floor (only files the simulator itself created — tracked in a ledger — are ever deleted). State (cursors, last tick, ledger) persists in `<data>/sim_state/state.json`, so restarts resume where they left off; on startup the most recent aligned tick is emitted immediately (catch-up).

## Quick start

Prerequisites: Docker (with Compose), `make`, your **read-only master raw-data folders** on the VPS, and the **tiles-processor data dir** the producer watches (a Docker named volume, or any host dir).

```bash
# 1. Clone
git clone <repo-url> data-simulator
cd data-simulator

# 2. Configure — point at your read-only master folders and the tiles-processor data
cp .env.example .env
$EDITOR .env     # set GLM_SEED_DIR / RADAR_SEED_DIR / WRF_SEED_DIR + TILES_DATA_DIR

# 3. Boot
make up          # build + start the container (detached)

# 4. Verify it's emitting
make status      # per-source cursors, last/next tick, emitted counts
make logs        # follow the tick logs
```

No data is moved or migrated — the master folders are mounted **read-only** and only ever read. After `make up` the simulator immediately emits the most recent aligned tick for every source (catch-up), then keeps ticking on schedule (GLM/radar every 10 min, WRF every 6 h). The tiles-processor producer picks the new files up on its next scan — no tiles-processor config changes, it keeps watching `data/{glm_h5,radar_h5,wrf_nc}`.

### Hardlink vs copy

The emitter hardlinks radar/WRF (instant, zero extra disk) **only when the master folders and the tiles-processor data dir are on the same filesystem**. On the Hetzner deployment they are not — the master raw data sits on the root partition while the Docker volumes live on a mounted block volume — so `settings.json` ships with `"link_mode": "copy"`. (Cross-filesystem hardlinks fail with `EXDEV`; symlinks can't bridge it either, because the producer container doesn't mount the master folders.) GLM always copies regardless (it rewrites the file's time attrs).

Disk cost of copy mode (on the volume): each WRF tick copies one full run (146 files, ~6.3 GB). Every tick the simulator copies the **new** run in and then prunes its own emissions older than the retention window — disk is bounded, not append-only (it only ever deletes files it created, never the master or tiles-processor's outputs). Because retention is a count-based ring (keep the newest `wrf.retention_ticks` runs) that prunes *after* the copy, the default `wrf.retention_ticks: 5` keeps **5 runs (~31 GB)** at steady state and peaks at **6 runs (~38 GB)** for the moment between copy and prune. Size the volume for the peak, or lower `wrf.retention_ticks` (4 → ~25 GB, 3 → ~19 GB). The `wrf.retention_minutes: 1080` floor is a safety net that only binds if ticks ever arrive faster than the 6 h interval — at the normal cadence the ring is the active bound. Radar/GLM copies are small. If you ever move the master data onto the same volume, flip `link_mode` back to `hardlink` and the WRF copies become free hardlinks.

> Note: pruning relies on the ledger in `sim_state/state.json` (on the volume). If that state file is deleted, the simulator forgets its past emissions and won't prune them — you'd clean up stale `wrf_nc/*` copies manually.

If the data dir is owned by another user, add `user: "${UID}:${GID}"` to the service in `docker-compose.yaml`.

Finding the tiles-processor volume path (Coolify/Docker named volume):

```bash
docker volume ls | grep tiles-data
# → use /var/lib/docker/volumes/<name>/_data as TILES_DATA_DIR
```

### Make targets

| Target | What it does |
|---|---|
| `make up` | Build and start the simulator (detached). |
| `make down` | Stop and remove the container. |
| `make restart` | Restart — picks up `settings.json` edits without a rebuild. |
| `make logs` | Follow the tick logs. |
| `make status` | Pretty-print `/status` for all sources. |
| `make tick SRC=radar` | Force a tick now for one source (`glm`\|`radar`\|`wrf`). |
| `make install` | Create the local `.venv` and install dev deps. |
| `make test` | Run the test suite with coverage (same command as CI). |
| `make clean` | Stop the container and remove orphans. |

## Configuration

Same scheme as tiles-processor: tunables live in **`settings.json`** (mounted into the container — edit + restart, no rebuild); `.env` holds only deployment values (`TILES_DATA_DIR`, `SIM_PORT`). Every scalar in settings.json can also be overridden with an env var (env > settings.json > built-in default):

| settings.json | env override |
|---|---|
| `link_mode` | `SIM_LINK_MODE` |
| `<src>.enabled` | `SIM_<SRC>_ENABLED` |
| `<src>.interval_minutes` | `SIM_<SRC>_INTERVAL_MINUTES` |
| `<src>.retention_minutes` | `SIM_<SRC>_RETENTION_MINUTES` |
| `<src>.retention_ticks` | `SIM_<SRC>_RETENTION_TICKS` |
| `glm.accum_minutes` | `SIM_GLM_ACCUM_MINUTES` |
| `wrf.expected_forecast_hours` | `SIM_WRF_EXPECTED_HOURS` |
| `radar.subvolume_offsets_seconds` | — (settings.json only) |

`glm.accum_minutes` must match the producer's GLM window size.

Paths are env-only (not in settings.json):

| Env var | Default | Points at |
|---|---|---|
| `SIM_DATA_ROOT` | `/data` | Emission target root (producer's watched dirs live here). |
| `SIM_GLM_SEED_DIR` | `$SIM_SEED_DIR/glm_h5` | Master GLM folder (`*.nc`). |
| `SIM_RADAR_SEED_DIR` | `$SIM_SEED_DIR/radar_h5` | Master radar folder (`RMAx/*.H5`). |
| `SIM_WRF_SEED_DIR` | `$SIM_SEED_DIR/wrf_nc` | Master WRF folder (`*FIELD2D*.nc` + FIELD3D siblings). |
| `SIM_SEED_DIR` | `$SIM_DATA_ROOT/seed` | Base for the three seed defaults above; set this alone if all three sit under one root. |
| `SIM_STATE_FILE` | `$SIM_DATA_ROOT/sim_state/state.json` | Cursor/ledger state (must be writable). |
| `SIM_SETTINGS_PATH` | `./settings.json` | Tunables file. |

The compose file maps your three host folders to `/seed/glm_h5`, `/seed/radar_h5`, `/seed/wrf_nc` (read-only) and sets the matching `SIM_*_SEED_DIR` vars, so the host folders can live anywhere.

## API (port 6030)

- `GET /health` — liveness
- `GET /status` — per source: last/next tick, cursor positions + direction, emitted totals, ledger size, last error
- `POST /tick/{glm|radar|wrf}` — force a tick now (409 if one is running). Radar/WRF can be forced freely; forcing GLM more than once inside the same 10-minute wall-clock window rebuilds the same filenames (overwrite-skip, no new window).

## Notes

- GLM windows become eligible for the producer ~30 s after the tick (its safety lag) and are discovered on its next 5-min scan — up to ~5 min latency is normal.
- At a ping-pong turnaround the weather plays in reverse for one pass; intra-window GLM file order is reversed too so motion stays continuous.
- `link_mode` is `copy` by default for the cross-filesystem Hetzner layout (see [Hardlink vs copy](#hardlink-vs-copy)); `hardlink` is the better choice when master data and the data volume share a filesystem.
- Filename formats are mirrored from `tiles-processor/src/models/{radar_config,wrf_config}.py`, `src/models/glm_folder_config.py`; window semantics from `src/data_sources/glm_folder.py`; attr contract from `src/services/glm_aggregation.py`.

## Development

```bash
make install     # python3 -m venv .venv && pip install -r requirements-dev.txt
make test        # pytest with coverage (reports/)
```

CI mirrors this: `.github/workflows/test.yml` runs gitleaks + the test suite on every branch/PR; `.github/workflows/security.yml` re-runs the suite and a Trivy image scan on `main`.

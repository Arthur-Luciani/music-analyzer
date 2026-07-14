# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Music Analyzer: given a search query or YouTube URL, it downloads the audio (yt-dlp), separates it into stems with Demucs (vocals/drums/bass/other), and runs a drum-specific analysis pipeline (ML onset/hit classification + groove pattern extraction) that can be transcribed to MIDI/MusicXML and corrected manually. Users track long-running jobs live over a WebSocket, and can duplicate/reprocess sessions, adjust a per-stem mix, and export a mixed master.

Backend: FastAPI + SQLAlchemy/Alembic (SQLite). Frontend: React + Vite, wavesurfer.js for waveforms.

## Commands

Local dev (Windows, no Docker) — starts both services with correct storage/GPU env vars in separate windows:
```powershell
.\run-local-dev.ps1 -Target all -SeparationDevice cuda   # or -SeparationDevice cpu
.\run-local-dev.ps1 -Target backend -SeparationDevice cuda
.\run-local-dev.ps1 -Target frontend
.\run-local-dev.ps1 -Target check     # curls health endpoints for both services
.\run-local-dev.ps1 -InstallDeps ...  # add to any target to pip install / npm install first
```

Manual backend run:
```bash
cd backend
pip install -r requirements.txt -r requirements.pipeline.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
requirements.txt has the API/DB deps; requirements.pipeline.txt has the heavy ML pipeline deps (torch cu118, demucs, yt-dlp, librosa) and is intentionally split out so the API can be developed without them installed.

Docker (needs NVIDIA Container Toolkit for GPU):
```bash
docker compose build
docker compose up
```

Tests (no pytest.ini — plain pytest, run from `backend/`):
```bash
cd backend
python -m pytest                                    # all tests
python -m pytest tests/test_session_repository.py    # one file
python -m pytest tests/test_session_repository.py::test_create_and_get_session  # one test
```
Repository/service tests spin up an in-memory SQLite engine (`create_engine("sqlite:///:memory:")` + `Base.metadata.create_all`) rather than mocking the ORM — follow that pattern for new persistence tests.

DB migrations (Alembic, config at `backend/alembic.ini`, targets `../storage/sessions.db`):
```bash
cd backend
alembic revision -m "description"
alembic upgrade head
```

Frontend:
```bash
cd frontend
npm install
npm run dev       # vite dev server on :5173
npm run build
```

FFmpeg must be on PATH for local (non-Docker) separation; `run-local-dev.ps1` auto-detects a winget-installed FFmpeg and sets `FFMPEG_BINARY`/PATH for the backend process. If yt-dlp reports a YouTube login/cookie requirement, export browser cookies and set `YTDLP_COOKIE_FILE`.

## Architecture

### Backend layering (`backend/app/`)

Strict one-way dependency chain — routes never touch the DB or repository directly, and use cases never talk to each other except through `JobService`:

```
main.py (routes)  →  services/jobs.py (JobService)  →  use_cases/*  →  repositories/session_repository.py  →  db/models.py (SQLAlchemy ORM)
```

- **`main.py`**: thin FastAPI routes. All logic is delegated to the singleton `job_service` (`services/jobs.py`).
- **`services/jobs.py`**: `JobService` is the orchestrator. It holds in-memory job state (`_jobs` dict) for fast reads plus a `SessionRepository` for persistence, and a pub/sub `_subscribers` map of `asyncio.Queue` per job for the `/ws/{job_id}` WebSocket. On init it instantiates every use case, injecting itself (`UseCase(self)`) so use cases can call back into `job_service.update_job(...)` to push state/progress and fan out WS events.
- **`use_cases/`**: one class per operation (`ProcessSessionUseCase`, `AnalyzeDrumStemUseCase`, `GenerateDrumMidiUseCase`, `RunExportUseCase`, etc.), each a `@dataclass` holding a `_job_service` back-reference. This is where the actual pipeline steps live (yt-dlp download, Demucs invocation, ffmpeg mixdown, ML drum analysis).
- **`repositories/session_repository.py`**: only place that talks SQLAlchemy. Sessions, mix state, export jobs and session events are separate ORM tables (`db/models.py`) all keyed off `session_id`, with `SessionEventORM` acting as an append-only progress log.
- **`models/`**: Pydantic request/response models (`session.py`, `mix.py`, `export.py`, `drum_analysis.py`, `search.py`, `common.py`), re-exported from `models/__init__.py`. These are distinct from the ORM models in `db/models.py` — don't conflate the two "models".
- **`ml/`**: trained drum-hit classifier (`drum_classifier.pth`) used by `analyze_drum_stem.py` / `extract_groove_patterns.py`, built on top of `adtof-pytorch`.

### Processing pipeline (`use_cases/process_session.py`)

`ProcessSessionUseCase.execute()` runs as a FastAPI `BackgroundTasks` job and drives the job through `JobState`: `downloading → separating → ready` (or `failed`), pushing progress via `job_service.update_job()` after each step:
1. yt-dlp downloads best audio to `storage/raw/{job_id}/source.*`.
2. Demucs separates stems; device selection tries `cuda` then falls back to `cpu` when `SEPARATION_DEVICE=auto` (`_resolve_demucs_devices`). Stems are compressed to MP3 via ffmpeg and written to `storage/stems/{job_id}/{stem}.mp3`.
3. A silent mixdown is produced and probed with ffmpeg's `loudnorm` filter to compute `MasterMetrics` (LUFS, true peak, headroom).

Drum analysis (`analyze_drum_stem.py`, `extract_groove_patterns.py`, `generate_drum_midi.py`) runs as a separate, later background task triggered from `POST /api/sessions/{id}/drum-analysis` — it is not part of the main processing job.

### Configuration (`backend/app/settings.py`)

A single frozen `Settings` dataclass loaded once at import time from env vars (`SEPARATION_MODEL`, `SEPARATION_DEVICE`, `SEPARATION_SEGMENT`, `SEPARATION_OVERLAP`, `SEPARATION_SHIFTS`, `SEPARATION_TARGET_STEMS`, `STORAGE_ROOT`, `TORCH_HOME`, `YTDLP_COOKIE_FILE`). `STORAGE_ROOT` defaults to `storage/` resolved against the repo root, not the CWD — relevant if you add a script that imports `app.settings` from elsewhere.

### Frontend (`frontend/src/`)

Pattern: `pages/` (route-level) → `containers/` (data-fetching + wiring) → presentational `components/`, with `hooks/` for stateful logic (`useProcessing`, `useWorkspace`, `useWebAudioMixer`, `useSessionEvents`) and `context/` for cross-page state (`SessionContext`, `ProcessingContext`). `api.js` is the single fetch/WebSocket client for the backend — all HTTP calls go through it, no direct `fetch()` elsewhere. Requests are made to relative paths (`/api/...`); Vite/docker-compose proxy or `VITE_BACKEND_ORIGIN` handles routing to the backend origin.

### Storage layout

`storage/raw/{job_id}/` (downloaded source audio), `storage/stems/{job_id}/{stem}.mp3` (+ `samples/`, drum analysis artifacts), `storage/exports/`, `storage/cache/torch/` (Demucs model cache), `storage/sessions.db` (SQLite). All of `storage/*` except `.gitkeep` files is gitignored.

## Known gotchas

- `docs/refactoring/*` describes an ORM/use-case extraction as **still pending** — it isn't; that refactor is already implemented in current `main`. Don't treat those docs as a live plan; check the actual code under `backend/app/` instead.
- `storage/sessions.db-shm` / `-wal` (SQLite WAL sidecar files) are currently tracked in git even though `sessions.db` itself is ignored — they churn on every write, so don't be surprised by unrelated diffs there.

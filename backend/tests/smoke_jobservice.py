#!/usr/bin/env python3
import os
import asyncio
import tempfile
from pathlib import Path

# Use an isolated temp DB for the smoke test
tmpdir = tempfile.mkdtemp()
db_path = Path(tmpdir) / "sessions.db"
os.environ["SESSIONS_DB_PATH"] = str(db_path)

# Create tables based on ORM metadata
from app.db.config import engine, Base
Base.metadata.create_all(bind=engine)

from app.services.jobs import JobService
from app.models import SearchCandidate

svc = JobService()

cand = SearchCandidate(
    source_id="yt_smoke",
    source="youtube",
    title="Smoke Test",
    artist="Smoke Artist",
    duration_seconds=1,
    url="https://example.com/smoke",
)

job = asyncio.run(svc.create_job("smoke", selected_track=cand))
print("SMOKE_OK", job.session_code)

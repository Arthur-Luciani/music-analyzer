from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.models import ExportState, JobState, SearchCandidate
from app.repositories.session_repository import SessionRepository


@pytest.fixture()
def repo():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    repo = SessionRepository(db_session=session)
    try:
        yield repo
    finally:
        session.close()


def test_create_and_get_session(repo: SessionRepository):
    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )

    code = repo.create_session(
        session_id="test-1",
        query="test query",
        selected_track=cand,
        target_stems=["vocals", "drums"],
        state=JobState.queued,
        progress=0,
        message="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert code.startswith("MX-")

    loaded = repo.get_session("test-1")
    assert loaded is not None
    assert loaded.session_code == code
    assert loaded.query == "test query"


def test_list_sessions_with_filter(repo: SessionRepository):
    now = datetime.utcnow()
    for i in range(3):
        cand = SearchCandidate(
            source_id=f"yt_{i}",
            source="youtube",
            title=f"Song {i}",
            artist=f"Artist {i}",
            duration_seconds=100,
            url=f"https://example.com/{i}",
        )
        repo.create_session(
            session_id=f"test-{i}",
            query=f"query {i}",
            selected_track=cand,
            target_stems=["vocals"],
            state=JobState.queued if i < 2 else JobState.ready,
            progress=0 if i < 2 else 100,
            message="test",
            created_at=now,
            updated_at=now,
        )

    items, total = repo.list_sessions(
        query=None,
        status=JobState.ready,
        created_from=None,
        created_to=None,
        page=1,
        page_size=10,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].state == JobState.ready


def test_mix_state_persistence(repo: SessionRepository):
    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )

    repo.create_session(
        session_id="test-mix",
        query="test",
        selected_track=cand,
        target_stems=["vocals"],
        state=JobState.queued,
        progress=0,
        message="test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    payload = {"per_stem": {"vocals": {"gain": 3.0}}, "master_gain": -1.5}
    repo.save_mix_state_payload("test-mix", payload, datetime.utcnow())

    loaded = repo.get_mix_state_payload("test-mix")
    assert loaded is not None
    assert float(loaded["master_gain"]) == -1.5


def test_export_job_lifecycle(repo: SessionRepository):
    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )

    repo.create_session(
        session_id="test-export",
        query="test",
        selected_track=cand,
        target_stems=["vocals"],
        state=JobState.ready,
        progress=100,
        message="done",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    export_job = repo.create_export_job(
        export_id="exp-1",
        session_id="test-export",
        preset="study_mix",
        format_name="wav",
        state=ExportState.queued,
        progress=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    export_job.state = ExportState.ready
    export_job.progress = 100
    repo.save_export_job(export_job)

    loaded = repo.get_export_job("test-export", "exp-1")
    assert loaded is not None
    assert loaded.state == ExportState.ready

    jobs = repo.list_export_jobs("test-export")
    assert len(jobs) == 1
    assert jobs[0].export_id == "exp-1"

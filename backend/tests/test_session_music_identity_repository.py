from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.repositories.session_repository import SessionRepository
from app.repositories.session_music_identity_repository import SessionMusicIdentityRepository
from app.models import JobState, SearchCandidate


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def repo(db_session):
    return SessionMusicIdentityRepository(db_session=db_session)


def _create_session(db_session, session_id: str) -> None:
    from datetime import datetime

    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )
    SessionRepository(db_session=db_session).create_session(
        session_id=session_id,
        query="test query",
        selected_track=cand,
        target_stems=["drums"],
        state=JobState.queued,
        progress=0,
        message="Job queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_get_returns_none_when_no_identity_saved(repo: SessionMusicIdentityRepository, db_session):
    _create_session(db_session, "s1")
    assert repo.get("s1") is None


def test_upsert_then_get_roundtrips(repo: SessionMusicIdentityRepository, db_session):
    _create_session(db_session, "s1")
    repo.upsert("s1", artist_id=42, artist_text="Survivor", title_text="Eye Of The Tiger", source_url="https://x")

    saved = repo.get("s1")
    assert saved is not None
    assert saved.artist_id == 42
    assert saved.artist_text == "Survivor"
    assert saved.title_text == "Eye Of The Tiger"
    assert saved.source_url == "https://x"
    assert saved.track_id is None
    assert saved.resolved_midi_file_id is None


def test_upsert_overwrites_previous_identity(repo: SessionMusicIdentityRepository, db_session):
    _create_session(db_session, "s1")
    repo.upsert("s1", artist_id=1, artist_text="A", title_text="B", source_url=None)
    repo.upsert("s1", artist_id=2, artist_text="C", title_text="D", source_url=None)

    saved = repo.get("s1")
    assert saved.artist_id == 2
    assert saved.artist_text == "C"
    assert saved.title_text == "D"


def test_set_resolution_updates_track_and_file(repo: SessionMusicIdentityRepository, db_session):
    from datetime import datetime

    _create_session(db_session, "s1")
    repo.upsert("s1", artist_id=1, artist_text="A", title_text="B", source_url=None)

    now = datetime.utcnow()
    repo.set_resolution("s1", track_id=10, resolved_midi_file_id=20, resolved_at=now)

    saved = repo.get("s1")
    assert saved.track_id == 10
    assert saved.resolved_midi_file_id == 20
    assert saved.resolved_at is not None


def test_set_resolution_is_noop_when_no_identity_row(repo: SessionMusicIdentityRepository, db_session):
    from datetime import datetime

    _create_session(db_session, "s1")
    # Não lança mesmo sem upsert prévio — só não faz nada.
    repo.set_resolution("s1", track_id=10, resolved_midi_file_id=20, resolved_at=datetime.utcnow())
    assert repo.get("s1") is None


def test_get_many_returns_only_sessions_with_saved_identity(repo: SessionMusicIdentityRepository, db_session):
    _create_session(db_session, "s1")
    _create_session(db_session, "s2")
    _create_session(db_session, "s3")
    repo.upsert("s1", artist_id=1, artist_text="Survivor", title_text="Eye Of The Tiger", source_url=None)
    repo.upsert("s3", artist_id=2, artist_text="Coldplay", title_text="Yellow", source_url=None)

    result = repo.get_many(["s1", "s2", "s3"])

    assert set(result.keys()) == {"s1", "s3"}
    assert result["s1"].artist_text == "Survivor"
    assert result["s3"].title_text == "Yellow"


def test_get_many_empty_list_returns_empty_dict(repo: SessionMusicIdentityRepository):
    assert repo.get_many([]) == {}

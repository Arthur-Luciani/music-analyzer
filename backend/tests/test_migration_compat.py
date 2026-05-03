from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.models import JobState, SearchCandidate
from app.repositories.session_repository import SessionRepository
from app.repositories.session_store import SQLiteSessionStore


def test_compat_with_legacy_store(tmp_path):
    db_path = tmp_path / "sessions.db"
    legacy = SQLiteSessionStore(db_path)

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    session = SessionLocal()
    repo = SessionRepository(db_session=session)

    cand = SearchCandidate(
        source_id="yt_compat",
        source="youtube",
        title="Compatibility Test",
        artist="Test Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )

    code_orm = repo.create_session(
        session_id="compat-orm-1",
        query="compat test",
        selected_track=cand,
        target_stems=["vocals"],
        state=JobState.queued,
        progress=0,
        message="test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    loaded_legacy = legacy.get_session("compat-orm-1")

    session.close()

    assert loaded_legacy is not None
    assert code_orm == loaded_legacy.session_code

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.models import MusicIdentityRequest
from app.repositories.market_midi_repository import MarketMidiRepository
from app.repositories.session_music_identity_repository import SessionMusicIdentityRepository
from app.services.market_midi_matcher import normalize_artist
from app.use_cases.save_music_identity import SaveMusicIdentityUseCase


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def repo(db_session_factory):
    return MarketMidiRepository(session_factory=db_session_factory)


@pytest.fixture()
def identity_repo(db_session_factory):
    return SessionMusicIdentityRepository(session_factory=db_session_factory)


def test_uses_given_artist_id_without_touching_catalog(repo, identity_repo):
    artist_id = repo.get_or_create_artist("Survivor", normalize_artist("Survivor"))
    use_case = SaveMusicIdentityUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo)

    result = use_case.execute(
        "session-1",
        MusicIdentityRequest(artist_text="Survivor", title_text="Eye Of The Tiger", artist_id=artist_id),
    )

    assert result.artist_id == artist_id
    assert result.title_text == "Eye Of The Tiger"


def test_resolves_existing_catalog_artist_by_exact_normalized_name(repo, identity_repo):
    artist_id = repo.get_or_create_artist("Survivor", normalize_artist("Survivor"))
    use_case = SaveMusicIdentityUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo)

    # No artist_id given, but the text matches an existing catalog artist exactly.
    result = use_case.execute(
        "session-1",
        MusicIdentityRequest(artist_text="Survivor", title_text="Eye Of The Tiger"),
    )

    assert result.artist_id == artist_id


def test_creates_user_created_artist_when_no_catalog_match(repo, identity_repo):
    use_case = SaveMusicIdentityUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo)

    result = use_case.execute(
        "session-1",
        MusicIdentityRequest(artist_text="Some Obscure Local Band", title_text="Unreleased Demo"),
    )

    assert result.artist_id is not None
    artists = repo.list_all_artists()
    created = next(a for a in artists if a.id == result.artist_id)
    assert created.name == "Some Obscure Local Band"


def test_persists_source_url(repo, identity_repo):
    use_case = SaveMusicIdentityUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo)

    result = use_case.execute(
        "session-1",
        MusicIdentityRequest(artist_text="Band", title_text="Song", source_url="https://youtube.com/watch?v=x"),
    )

    assert result.source_url == "https://youtube.com/watch?v=x"
    saved = identity_repo.get("session-1")
    assert saved.source_url == "https://youtube.com/watch?v=x"

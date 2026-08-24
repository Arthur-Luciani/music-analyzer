from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datetime import datetime

from app.db.config import Base
from app.db.models import SessionORM
from app.models import MarketArtistUpdate, MarketTrackUpdate
from app.repositories.market_midi_repository import MarketMidiRepository
from app.repositories.session_music_identity_repository import SessionMusicIdentityRepository
from app.services.market_midi_matcher import normalize_artist, normalize_title
from app.use_cases.manage_market_catalog import (
    DeleteMarketArtistUseCase,
    DeleteMarketMidiFileUseCase,
    DeleteMarketTrackUseCase,
    GetMarketArtistUseCase,
    GetMarketTrackUseCase,
    ListMarketArtistsUseCase,
    ListMarketTracksUseCase,
    UpdateMarketArtistUseCase,
    UpdateMarketTrackUseCase,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


@pytest.fixture()
def repo(db_session):
    return MarketMidiRepository(db_session=db_session)


@pytest.fixture()
def identity_repo(db_session):
    return SessionMusicIdentityRepository(db_session=db_session)


def _seed_session(db_session, session_id: str, *, session_code: str, track_title: str, artist: str, state: str = "ready") -> None:
    now = datetime.utcnow()
    db_session.add(
        SessionORM(
            id=session_id,
            session_code=session_code,
            query=f"{artist} {track_title}",
            track_title=track_title,
            artist=artist,
            target_stems_json="[]",
            state=state,
            progress=100,
            message="",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()


def _seed_track(repo: MarketMidiRepository, artist_name: str, title: str, *, files: int = 1) -> tuple[int, int]:
    artist_id = repo.get_or_create_artist(artist_name, normalize_artist(artist_name))
    track_id = repo.get_or_create_track(artist_id, title, normalize_title(title))
    for i in range(files):
        repo.add_midi_file(track_id, f"{artist_name}/{title}/{i}.mid")
    return artist_id, track_id


def test_list_artists_paginates_and_reports_track_count(repo: MarketMidiRepository):
    _seed_track(repo, "Survivor", "Eye of the Tiger")
    _seed_track(repo, "Survivor", "Burning Heart")
    _seed_track(repo, "Coldplay", "Yellow")

    result = ListMarketArtistsUseCase(_job_service=None, _repository=repo).execute(query=None, page=1, page_size=20)

    assert result.total == 2
    survivor = next(item for item in result.items if item.name == "Survivor")
    assert survivor.track_count == 2


def test_list_artists_filters_by_query(repo: MarketMidiRepository):
    _seed_track(repo, "Survivor", "Eye of the Tiger")
    _seed_track(repo, "Coldplay", "Yellow")

    result = ListMarketArtistsUseCase(_job_service=None, _repository=repo).execute(query="cold", page=1, page_size=20)

    assert result.total == 1
    assert result.items[0].name == "Coldplay"


def test_get_artist_returns_tracks_with_midi_counts(repo: MarketMidiRepository):
    artist_id, _ = _seed_track(repo, "Survivor", "Eye of the Tiger", files=3)

    detail = GetMarketArtistUseCase(_job_service=None, _repository=repo).execute(artist_id)

    assert detail is not None
    assert detail.name == "Survivor"
    assert len(detail.tracks) == 1
    assert detail.tracks[0].midi_file_count == 3


def test_get_artist_missing_returns_none(repo: MarketMidiRepository):
    assert GetMarketArtistUseCase(_job_service=None, _repository=repo).execute(999) is None


def test_rename_artist_updates_name_and_norm(repo: MarketMidiRepository):
    artist_id, _ = _seed_track(repo, "Survivorr", "Eye of the Tiger")

    updated = UpdateMarketArtistUseCase(_job_service=None, _repository=repo).execute(
        artist_id, MarketArtistUpdate(name="Survivor")
    )

    assert updated.name == "Survivor"
    # o nome renomeado agora resolve nas buscas fuzzy do wizard
    artists = repo.list_all_artists()
    assert artists[0].name_norm == normalize_artist("Survivor")


def test_rename_artist_to_duplicate_name_raises(repo: MarketMidiRepository):
    _seed_track(repo, "Survivor", "Eye of the Tiger")
    other_id, _ = _seed_track(repo, "Coldplay", "Yellow")

    with pytest.raises(ValueError):
        UpdateMarketArtistUseCase(_job_service=None, _repository=repo).execute(
            other_id, MarketArtistUpdate(name="Survivor")
        )


def test_delete_artist_cascades_to_tracks_and_files(repo: MarketMidiRepository, identity_repo):
    artist_id, track_id = _seed_track(repo, "Survivor", "Eye of the Tiger", files=2)

    deleted = DeleteMarketArtistUseCase(_job_service=None, _repository=repo).execute(artist_id)

    assert deleted is True
    assert GetMarketArtistUseCase(_job_service=None, _repository=repo).execute(artist_id) is None
    assert GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id) is None


def test_delete_artist_missing_returns_false(repo: MarketMidiRepository):
    assert DeleteMarketArtistUseCase(_job_service=None, _repository=repo).execute(999) is False


def test_list_tracks_filters_by_artist(repo: MarketMidiRepository):
    survivor_id, _ = _seed_track(repo, "Survivor", "Eye of the Tiger")
    _seed_track(repo, "Coldplay", "Yellow")

    result = ListMarketTracksUseCase(_job_service=None, _repository=repo).execute(
        artist_id=survivor_id, query=None, page=1, page_size=20
    )

    assert result.total == 1
    assert result.items[0].title == "Eye of the Tiger"
    assert result.items[0].artist_name == "Survivor"


def test_list_tracks_handles_same_artist_across_multiple_rows(repo: MarketMidiRepository):
    # Regressão: o join track+artist repete o mesmo MarketArtistORM em cada
    # linha quando o artista tem mais de uma música — um segundo
    # `session.expunge()` no mesmo objeto derruba a query (InvalidRequestError).
    survivor_id, _ = _seed_track(repo, "Survivor", "Eye of the Tiger")
    _seed_track(repo, "Survivor", "Burning Heart")

    result = ListMarketTracksUseCase(_job_service=None, _repository=repo).execute(
        artist_id=None, query=None, page=1, page_size=20
    )

    assert result.total == 2
    assert {item.title for item in result.items} == {"Eye of the Tiger", "Burning Heart"}


def test_get_track_lists_midi_files(repo: MarketMidiRepository, identity_repo):
    _, track_id = _seed_track(repo, "Survivor", "Eye of the Tiger", files=2)

    detail = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id)

    assert detail is not None
    assert detail.artist_name == "Survivor"
    assert len(detail.midi_files) == 2


def test_rename_track_and_reassign_artist(repo: MarketMidiRepository, identity_repo):
    _, track_id = _seed_track(repo, "Survivor", "Eye of the Tigger")
    coldplay_id, _ = _seed_track(repo, "Coldplay", "Yellow")

    updated = UpdateMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(
        track_id, MarketTrackUpdate(title="Eye of the Tiger", artist_id=coldplay_id)
    )

    assert updated.title == "Eye of the Tiger"
    assert updated.artist_id == coldplay_id
    assert updated.artist_name == "Coldplay"


def test_delete_track_cascades_to_midi_files(repo: MarketMidiRepository, identity_repo):
    _, track_id = _seed_track(repo, "Survivor", "Eye of the Tiger", files=2)
    detail_before = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id)
    file_id = detail_before.midi_files[0].id

    deleted = DeleteMarketTrackUseCase(_job_service=None, _repository=repo).execute(track_id)

    assert deleted is True
    assert GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id) is None
    assert repo.update_file_probe_result(file_id, has_drum_track=True, duration_seconds=1.0) is None  # no-op, row gone


def test_delete_midi_file(repo: MarketMidiRepository, identity_repo):
    _, track_id = _seed_track(repo, "Survivor", "Eye of the Tiger", files=2)
    detail = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id)
    file_id = detail.midi_files[0].id

    deleted = DeleteMarketMidiFileUseCase(_job_service=None, _repository=repo).execute(file_id)

    assert deleted is True
    remaining = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id)
    assert len(remaining.midi_files) == 1


def test_get_track_reports_linked_sessions_per_midi_file(repo: MarketMidiRepository, identity_repo, db_session):
    _, track_id = _seed_track(repo, "Survivor", "Eye of the Tiger", files=2)
    detail = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(track_id)
    linked_file_id = detail.midi_files[0].id
    unlinked_file_id = detail.midi_files[1].id

    _seed_session(db_session, "session-1", session_code="MX-001", track_title="Eye of the Tiger", artist="Survivor")
    identity_repo.upsert("session-1", artist_id=None, artist_text="Survivor", title_text="Eye of the Tiger", source_url=None)
    identity_repo.set_resolution(
        "session-1", track_id=track_id, resolved_midi_file_id=linked_file_id, resolved_at=datetime.utcnow()
    )

    updated = GetMarketTrackUseCase(_job_service=None, _repository=repo, _identity_repository=identity_repo).execute(
        track_id
    )

    linked = next(f for f in updated.midi_files if f.id == linked_file_id)
    unlinked = next(f for f in updated.midi_files if f.id == unlinked_file_id)
    assert len(linked.linked_sessions) == 1
    assert linked.linked_sessions[0].session_code == "MX-001"
    assert unlinked.linked_sessions == []

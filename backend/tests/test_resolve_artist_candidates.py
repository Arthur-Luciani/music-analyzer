from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.repositories.market_midi_repository import MarketMidiRepository
from app.services.market_midi_matcher import normalize_artist
from app.use_cases.resolve_artist_candidates import ResolveArtistCandidatesUseCase


@pytest.fixture()
def repo():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    return MarketMidiRepository(db_session=session)


def _seed_artists(repo: MarketMidiRepository, names: list[str]) -> None:
    for name in names:
        repo.get_or_create_artist(name, normalize_artist(name))


def test_ranks_close_matches_first(repo: MarketMidiRepository):
    _seed_artists(repo, ["Survivor", "Supertramp", "Coldplay"])
    use_case = ResolveArtistCandidatesUseCase(_job_service=None, _repository=repo)

    results = use_case.execute("Survivor Band")

    assert results
    assert results[0].name == "Survivor"


def test_returns_empty_list_when_nothing_plausible(repo: MarketMidiRepository):
    _seed_artists(repo, ["Survivor", "Supertramp", "Coldplay"])
    use_case = ResolveArtistCandidatesUseCase(_job_service=None, _repository=repo)

    results = use_case.execute("Totally Unrelated Query Xyz")

    assert results == []


def test_respects_limit(repo: MarketMidiRepository):
    _seed_artists(repo, ["Queen", "Queens of the Stone Age", "Queen Latifah", "Queen Naija"])
    use_case = ResolveArtistCandidatesUseCase(_job_service=None, _repository=repo)

    results = use_case.execute("Queen", limit=2)

    assert len(results) <= 2


def test_empty_query_returns_empty_list(repo: MarketMidiRepository):
    _seed_artists(repo, ["Survivor"])
    use_case = ResolveArtistCandidatesUseCase(_job_service=None, _repository=repo)

    assert use_case.execute("") == []

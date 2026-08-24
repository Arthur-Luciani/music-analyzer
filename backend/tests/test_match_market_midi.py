from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import Base
from app.models.drum_analysis import DrumAnalysis, DrumHit
from app.repositories.market_midi_repository import MarketMidiRepository
from app.services.market_midi_matcher import normalize_artist, normalize_title
from app.use_cases.match_market_midi import MatchMarketMidiUseCase


class _FakeSelectedTrack:
    def __init__(self, artist, title):
        self.artist = artist
        self.title = title


class _FakeJob:
    def __init__(self, artist, title):
        self.selected_track = _FakeSelectedTrack(artist, title) if (artist or title) else None


class _FakeJobService:
    def __init__(self, artist=None, title=None):
        self._artist = artist
        self._title = title

    async def get_job(self, session_id):
        return _FakeJob(self._artist, self._title)


@pytest.fixture()
def repo(tmp_path):
    # Arquivo real (não :memory:) — MatchMarketMidiUseCase.execute() roda a
    # busca numa thread de background (asyncio.to_thread), e um sqlite
    # :memory: compartilhado entre threads vira dois bancos vazios
    # diferentes (SQLAlchemy usa um pool por thread pra :memory:). Um
    # arquivo real não tem esse problema.
    db_path = tmp_path / "market_midi_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return MarketMidiRepository(session_factory=test_session_factory)


@pytest.fixture()
def isolated_settings(tmp_path):
    """Redireciona settings.stems_root/market_midi_root para tmp_path.

    `settings` é um dataclass frozen compartilhado por todos os módulos;
    usamos object.__setattr__ para contornar o frozen só durante o teste,
    e restauramos os valores originais no final.
    """
    from app.settings import settings as real_settings

    original_stems_root = real_settings.stems_root
    original_market_midi_root = real_settings.market_midi_root

    stems_root = tmp_path / "stems"
    market_midi_root = tmp_path / "market_midi"
    stems_root.mkdir(parents=True, exist_ok=True)
    market_midi_root.mkdir(parents=True, exist_ok=True)

    object.__setattr__(real_settings, "stems_root", stems_root)
    object.__setattr__(real_settings, "market_midi_root", market_midi_root)
    try:
        yield real_settings
    finally:
        object.__setattr__(real_settings, "stems_root", original_stems_root)
        object.__setattr__(real_settings, "market_midi_root", original_market_midi_root)


def _write_drum_analysis(stems_root, session_id: str, hits: list[DrumHit], duration_seconds: float, bpm: float = 120.0):
    session_dir = stems_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    analysis = DrumAnalysis(
        bpm=bpm,
        duration_seconds=duration_seconds,
        beat_count=len(hits),
        beats=[h.time for h in hits],
        hits=hits,
        analyzed_at=datetime.utcnow(),
        status="complete",
    )
    (session_dir / "drum_analysis.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")


def _seed_track(repo: MarketMidiRepository, artist: str, title: str) -> int:
    artist_id = repo.get_or_create_artist(artist, normalize_artist(artist))
    return repo.get_or_create_track(artist_id, title, normalize_title(title))


def _write_candidate_midi(market_midi_root, relative_path: str, note_times: list[float], bpm: float = 120.0):
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    for t in note_times:
        drums.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=t, end=t + 0.05))
    pm.instruments.append(drums)

    path = market_midi_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


def _write_empty_candidate_midi(market_midi_root, relative_path: str):
    """Um .mid válido mas sem nenhuma nota de bateria — simula um arquivo
    do dataset que não serve como candidato."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI()
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    pm.instruments.append(drums)
    path = market_midi_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


def _click_hits(n: int, period: float, offset: float = 0.0, scale: float = 1.0) -> list[float]:
    return [offset + scale * i * period for i in range(n)]


@pytest.mark.asyncio
async def test_returns_not_indexed_when_catalog_is_empty(isolated_settings, repo):
    use_case = MatchMarketMidiUseCase(_FakeJobService(artist="Any Artist", title="Any Song"), _repository=repo)
    result = await use_case.execute("session-not-indexed")
    assert result.status == "not_indexed"
    assert result.applied is False


@pytest.mark.asyncio
async def test_returns_no_match_when_query_does_not_match_catalog(isolated_settings, repo):
    _seed_track(repo, "Some Band", "Some Song")
    _write_drum_analysis(
        isolated_settings.stems_root,
        "session-no-match",
        hits=[DrumHit(time=i * 0.5, type="kick", velocity=0.8, confidence=1.0) for i in range(10)],
        duration_seconds=5.0,
    )

    use_case = MatchMarketMidiUseCase(
        _FakeJobService(artist="Totally Unrelated Artist", title="Nothing Alike"), _repository=repo
    )
    result = await use_case.execute("session-no-match")
    assert result.status == "no_match"
    assert result.applied is False


@pytest.mark.asyncio
async def test_returns_candidate_unreadable_when_midi_file_missing(isolated_settings, repo):
    track_id = _seed_track(repo, "Test Artist", "Test Song")
    repo.add_midi_file(track_id, "clean_midi/Test Artist/Test Song.mid")  # never written to disk
    _write_drum_analysis(
        isolated_settings.stems_root,
        "session-unreadable",
        hits=[DrumHit(time=i * 0.5, type="kick", velocity=0.8, confidence=1.0) for i in range(10)],
        duration_seconds=5.0,
    )

    use_case = MatchMarketMidiUseCase(_FakeJobService(artist="Test Artist", title="Test Song"), _repository=repo)
    result = await use_case.execute("session-unreadable")
    assert result.status == "candidate_unreadable"
    assert result.matched_artist == "Test Artist"


@pytest.mark.asyncio
async def test_returns_low_confidence_when_duration_incompatible(isolated_settings, repo):
    track_id = _seed_track(repo, "Test Artist", "Test Song")
    repo.add_midi_file(track_id, "clean_midi/Test Artist/Test Song.mid")
    _write_drum_analysis(
        isolated_settings.stems_root,
        "session-duration-mismatch",
        hits=[DrumHit(time=i * 0.5, type="kick", velocity=0.8, confidence=1.0) for i in range(20)],
        duration_seconds=10.0,
    )
    # Candidate is ~1s long vs. a 10s reference — well outside the compatible band.
    _write_candidate_midi(
        isolated_settings.market_midi_root,
        "clean_midi/Test Artist/Test Song.mid",
        note_times=[0.0, 0.5, 1.0],
    )

    use_case = MatchMarketMidiUseCase(_FakeJobService(artist="Test Artist", title="Test Song"), _repository=repo)
    result = await use_case.execute("session-duration-mismatch")
    assert result.status == "low_confidence"
    assert result.alignment_cost is None  # rejected before DTW even ran


@pytest.mark.asyncio
async def test_applies_market_midi_when_match_and_alignment_are_confident(isolated_settings, repo):
    ref_hits_times = _click_hits(20, period=0.5)
    ref_duration = 10.5

    track_id = _seed_track(repo, "Test Artist", "Test Song")
    repo.add_midi_file(track_id, "clean_midi/Test Artist/Test Song.mid")
    _write_drum_analysis(
        isolated_settings.stems_root,
        "session-applied",
        hits=[DrumHit(time=t, type="kick", velocity=0.8, confidence=1.0) for t in ref_hits_times],
        duration_seconds=ref_duration,
    )
    # Candidate: same rhythm, stretched (x1.2) and shifted (+0.3s) — a
    # plausible "different tempo/offset" market MIDI of the same song.
    cand_hits_times = _click_hits(20, period=0.5 * 1.2, offset=0.3)
    _write_candidate_midi(
        isolated_settings.market_midi_root,
        "clean_midi/Test Artist/Test Song.mid",
        note_times=cand_hits_times,
    )

    use_case = MatchMarketMidiUseCase(_FakeJobService(artist="Test Artist", title="Test Song"), _repository=repo)
    result = await use_case.execute("session-applied")

    assert result.status == "applied"
    assert result.applied is True
    assert result.matched_artist == "Test Artist"
    assert result.matched_title == "Test Song"

    output_path = isolated_settings.stems_root / "session-applied" / "drum_transcription.mid"
    assert output_path.is_file()

    sidecar_path = isolated_settings.stems_root / "session-applied" / "market_midi_match.json"
    assert sidecar_path.is_file()

    loaded = MatchMarketMidiUseCase.load_saved_result("session-applied")
    assert loaded is not None
    assert loaded.status == "applied"

    import pretty_midi
    warped = pretty_midi.PrettyMIDI(str(output_path))
    warped_notes = warped.instruments[0].notes
    assert len(warped_notes) > 0
    # Warped note times should land close to the original reference clicks.
    assert all(0.0 <= n.start <= ref_duration + 0.5 for n in warped_notes)


@pytest.mark.asyncio
async def test_skips_bad_candidate_file_and_applies_the_next_one(isolated_settings, repo):
    """N:1 — a track pode ter mais de um arquivo MIDI candidato (ex: duas
    transcrições do mesmo dataset). Um sem trilha de bateria não deve
    impedir o próximo candidato de ser tentado."""
    ref_hits_times = _click_hits(20, period=0.5)
    ref_duration = 10.5

    track_id = _seed_track(repo, "Test Artist", "Test Song")
    empty_file_id = repo.add_midi_file(track_id, "clean_midi/Test Artist/Test Song (empty).mid")
    good_file_id = repo.add_midi_file(track_id, "clean_midi/Test Artist/Test Song (good).mid")
    assert empty_file_id is not None and good_file_id is not None

    _write_drum_analysis(
        isolated_settings.stems_root,
        "session-n1",
        hits=[DrumHit(time=t, type="kick", velocity=0.8, confidence=1.0) for t in ref_hits_times],
        duration_seconds=ref_duration,
    )
    _write_empty_candidate_midi(isolated_settings.market_midi_root, "clean_midi/Test Artist/Test Song (empty).mid")
    cand_hits_times = _click_hits(20, period=0.5 * 1.2, offset=0.3)
    _write_candidate_midi(
        isolated_settings.market_midi_root,
        "clean_midi/Test Artist/Test Song (good).mid",
        note_times=cand_hits_times,
    )

    use_case = MatchMarketMidiUseCase(_FakeJobService(artist="Test Artist", title="Test Song"), _repository=repo)
    result = await use_case.execute("session-n1")

    assert result.status == "applied"
    assert result.applied is True

    files = repo.list_files_for_track(track_id)
    by_id = {f.id: f for f in files}
    assert by_id[empty_file_id].has_drum_track is False
    assert by_id[good_file_id].has_drum_track is True

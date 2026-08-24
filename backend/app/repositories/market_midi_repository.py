from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from app.db.config import SessionLocal
from app.db.models import MarketArtistORM, MarketMidiFileORM, MarketTrackORM


@dataclass(frozen=True)
class CatalogEntry:
    """Uma música (nível de track) do catálogo — granularidade usada pelo
    fuzzy match em market_midi_matcher.py. Uma track pode ter N arquivos
    MIDI candidatos (ver MidiFileEntry/list_files_for_track)."""
    artist_id: int
    artist: str
    artist_norm: str
    track_id: int
    title: str
    title_norm: str


@dataclass(frozen=True)
class MidiFileEntry:
    id: int
    relative_path: str
    has_drum_track: Optional[bool]
    duration_seconds: Optional[float]


class MarketMidiRepository:
    """ORM-backed repository para o catálogo de MIDI de mercado
    (market_artists -> market_tracks -> market_midi_files, N:1 em cada seta)."""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        session_factory: Optional[sessionmaker] = None,
    ) -> None:
        """`db_session` fixa uma única sessão compartilhada (uso síncrono,
        single-thread — ver test_session_repository.py para o padrão).
        `session_factory` abre uma sessão nova a cada chamada, fechando
        depois — necessário para MatchMarketMidiUseCase, que roda em thread
        de background (asyncio.to_thread): SQLAlchemy Session não é
        thread-safe, e um sqlite:///:memory: compartilhado entre threads
        vira, na prática, dois bancos separados (pool por thread)."""
        self._session = db_session
        self._session_factory = session_factory or SessionLocal

    def _get_session(self) -> Session:
        return self._session or self._session_factory()

    def is_empty(self) -> bool:
        """True se o catálogo ainda não foi importado (ver scripts/setup_market_midi.py)."""
        session = self._get_session()
        close_after = self._session is None
        try:
            return session.query(MarketArtistORM.id).first() is None
        finally:
            if close_after:
                session.close()

    def get_or_create_artist(self, name: str, name_norm: str, *, source: str = "catalog") -> int:
        session = self._get_session()
        close_after = self._session is None
        try:
            existing = session.query(MarketArtistORM).filter(MarketArtistORM.name_norm == name_norm).first()
            if existing:
                return existing.id
            artist = MarketArtistORM(name=name, name_norm=name_norm, source=source, created_at=datetime.utcnow())
            session.add(artist)
            session.commit()
            session.refresh(artist)
            return artist.id
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def get_or_create_track(self, artist_id: int, title: str, title_norm: str, *, source: str = "catalog") -> int:
        session = self._get_session()
        close_after = self._session is None
        try:
            existing = (
                session.query(MarketTrackORM)
                .filter(MarketTrackORM.artist_id == artist_id, MarketTrackORM.title_norm == title_norm)
                .first()
            )
            if existing:
                return existing.id
            track = MarketTrackORM(
                artist_id=artist_id,
                title=title,
                title_norm=title_norm,
                source=source,
                created_at=datetime.utcnow(),
            )
            session.add(track)
            session.commit()
            session.refresh(track)
            return track.id
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def add_midi_file(self, track_id: int, relative_path: str) -> Optional[int]:
        """Idempotente — retorna None sem inserir de novo se o path já estiver indexado
        (permite rodar o importador várias vezes sem duplicar linhas)."""
        session = self._get_session()
        close_after = self._session is None
        try:
            existing = (
                session.query(MarketMidiFileORM.id)
                .filter(MarketMidiFileORM.relative_path == relative_path)
                .first()
            )
            if existing:
                return None
            midi_file = MarketMidiFileORM(
                track_id=track_id,
                relative_path=relative_path,
                indexed_at=datetime.utcnow(),
            )
            session.add(midi_file)
            session.commit()
            session.refresh(midi_file)
            return midi_file.id
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def list_catalog_entries(self) -> list[CatalogEntry]:
        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(MarketTrackORM, MarketArtistORM)
                .join(MarketArtistORM, MarketTrackORM.artist_id == MarketArtistORM.id)
                .all()
            )
            return [
                CatalogEntry(
                    artist_id=artist.id,
                    artist=artist.name,
                    artist_norm=artist.name_norm,
                    track_id=track.id,
                    title=track.title,
                    title_norm=track.title_norm,
                )
                for track, artist in rows
            ]
        finally:
            if close_after:
                session.close()

    def list_files_for_track(self, track_id: int) -> list[MidiFileEntry]:
        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(MarketMidiFileORM)
                .filter(MarketMidiFileORM.track_id == track_id)
                .order_by(MarketMidiFileORM.id)
                .all()
            )
            return [
                MidiFileEntry(
                    id=row.id,
                    relative_path=row.relative_path,
                    has_drum_track=row.has_drum_track,
                    duration_seconds=row.duration_seconds,
                )
                for row in rows
            ]
        finally:
            if close_after:
                session.close()

    def update_file_probe_result(
        self, file_id: int, *, has_drum_track: bool, duration_seconds: Optional[float]
    ) -> None:
        """Cacheia o resultado de ler o arquivo (tem trilha de bateria? duração?) na
        primeira vez que ele é usado num match, pra não reabrir/reparsear em toda sessão."""
        session = self._get_session()
        close_after = self._session is None
        try:
            row = session.query(MarketMidiFileORM).filter(MarketMidiFileORM.id == file_id).first()
            if row is None:
                return
            row.has_drum_track = has_drum_track
            row.duration_seconds = duration_seconds
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

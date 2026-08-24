from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from app.db.config import SessionLocal
from app.db.models import SessionMusicIdentityORM


@dataclass(frozen=True)
class MusicIdentityEntry:
    session_id: str
    artist_id: Optional[int]
    artist_text: str
    title_text: str
    source_url: Optional[str]
    track_id: Optional[int]
    resolved_midi_file_id: Optional[int]
    resolved_at: Optional[datetime]


class SessionMusicIdentityRepository:
    """ORM-backed repository para `session_music_identity` (1:1 com sessions).

    Ver MarketMidiRepository para o porquê do `session_factory` — o mesmo
    cuidado de thread-safety se aplica aqui (match_market_midi.py roda em
    background thread)."""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        session_factory: Optional[sessionmaker] = None,
    ) -> None:
        self._session = db_session
        self._session_factory = session_factory or SessionLocal

    def _get_session(self) -> Session:
        return self._session or self._session_factory()

    def upsert(
        self,
        session_id: str,
        *,
        artist_id: Optional[int],
        artist_text: str,
        title_text: str,
        source_url: Optional[str],
    ) -> None:
        session = self._get_session()
        close_after = self._session is None
        try:
            now = datetime.utcnow()
            row = (
                session.query(SessionMusicIdentityORM)
                .filter(SessionMusicIdentityORM.session_id == session_id)
                .first()
            )
            if row is None:
                row = SessionMusicIdentityORM(session_id=session_id, created_at=now)
                session.add(row)
            row.artist_id = artist_id
            row.artist_text = artist_text
            row.title_text = title_text
            row.source_url = source_url
            row.updated_at = now
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def get(self, session_id: str) -> Optional[MusicIdentityEntry]:
        session = self._get_session()
        close_after = self._session is None
        try:
            row = (
                session.query(SessionMusicIdentityORM)
                .filter(SessionMusicIdentityORM.session_id == session_id)
                .first()
            )
            if row is None:
                return None
            return MusicIdentityEntry(
                session_id=row.session_id,
                artist_id=row.artist_id,
                artist_text=row.artist_text,
                title_text=row.title_text,
                source_url=row.source_url,
                track_id=row.track_id,
                resolved_midi_file_id=row.resolved_midi_file_id,
                resolved_at=row.resolved_at,
            )
        finally:
            if close_after:
                session.close()

    def set_resolution(
        self,
        session_id: str,
        *,
        track_id: Optional[int],
        resolved_midi_file_id: Optional[int],
        resolved_at: datetime,
    ) -> None:
        """Chamado pelo match_market_midi.py depois que o DTW confirma (ou
        descarta) qual track/arquivo é o certo pra essa sessão."""
        session = self._get_session()
        close_after = self._session is None
        try:
            row = (
                session.query(SessionMusicIdentityORM)
                .filter(SessionMusicIdentityORM.session_id == session_id)
                .first()
            )
            if row is None:
                return
            row.track_id = track_id
            row.resolved_midi_file_id = resolved_midi_file_id
            row.resolved_at = resolved_at
            row.updated_at = datetime.utcnow()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

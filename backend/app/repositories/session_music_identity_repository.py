from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from app.db.config import SessionLocal
from app.db.models import SessionMusicIdentityORM, SessionORM


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


@dataclass(frozen=True)
class LinkedSessionEntry:
    """Uma sessão que já resolveu (`resolved_midi_file_id`) pra um arquivo
    MIDI de mercado específico — usado pela tela de Catálogo pra mostrar se
    um arquivo já foi usado por alguma sessão real."""
    midi_file_id: int
    session_id: str
    session_code: str
    track_title: Optional[str]
    artist: Optional[str]
    state: str


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

    def get_many(self, session_ids: list[str]) -> dict[str, MusicIdentityEntry]:
        """Busca em lote pra listagens (ex: Biblioteca) — evita N+1 de
        `get()` por sessão exibida na página."""
        if not session_ids:
            return {}

        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(SessionMusicIdentityORM)
                .filter(SessionMusicIdentityORM.session_id.in_(session_ids))
                .all()
            )
            return {
                row.session_id: MusicIdentityEntry(
                    session_id=row.session_id,
                    artist_id=row.artist_id,
                    artist_text=row.artist_text,
                    title_text=row.title_text,
                    source_url=row.source_url,
                    track_id=row.track_id,
                    resolved_midi_file_id=row.resolved_midi_file_id,
                    resolved_at=row.resolved_at,
                )
                for row in rows
            }
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

    def list_sessions_for_midi_files(self, midi_file_ids: list[int]) -> dict[int, list[LinkedSessionEntry]]:
        """Pra cada arquivo MIDI de mercado, quais sessões já o usaram como
        transcrição vencedora (ver `set_resolution`, chamado por
        match_market_midi.py). Um arquivo pode ter 0, 1 ou mais sessões."""
        if not midi_file_ids:
            return {}

        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(SessionMusicIdentityORM, SessionORM)
                .join(SessionORM, SessionMusicIdentityORM.session_id == SessionORM.id)
                .filter(SessionMusicIdentityORM.resolved_midi_file_id.in_(midi_file_ids))
                .order_by(SessionORM.created_at.desc())
                .all()
            )

            result: dict[int, list[LinkedSessionEntry]] = {}
            for identity, session_row in rows:
                entry = LinkedSessionEntry(
                    midi_file_id=identity.resolved_midi_file_id,
                    session_id=session_row.id,
                    session_code=session_row.session_code,
                    track_title=session_row.track_title,
                    artist=session_row.artist,
                    state=session_row.state,
                )
                result.setdefault(entry.midi_file_id, []).append(entry)
            return result
        finally:
            if close_after:
                session.close()

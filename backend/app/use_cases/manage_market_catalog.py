from dataclasses import dataclass
from typing import Optional

from app.models import (
    MarketArtistDetail,
    MarketArtistListResponse,
    MarketArtistSummary,
    MarketArtistUpdate,
    MarketLinkedSession,
    MarketMidiFileSummary,
    MarketTrackDetail,
    MarketTrackListResponse,
    MarketTrackSummary,
    MarketTrackUpdate,
)
from app.repositories.market_midi_repository import MarketMidiRepository
from app.repositories.session_music_identity_repository import LinkedSessionEntry, SessionMusicIdentityRepository


def _artist_summary(artist, track_counts: dict[int, int]) -> MarketArtistSummary:
    return MarketArtistSummary(
        id=artist.id,
        name=artist.name,
        source=artist.source,
        created_at=artist.created_at,
        track_count=track_counts.get(artist.id, 0),
    )


def _track_summary(track, artist, midi_counts: dict[int, int]) -> MarketTrackSummary:
    return MarketTrackSummary(
        id=track.id,
        artist_id=track.artist_id,
        artist_name=artist.name,
        title=track.title,
        source=track.source,
        created_at=track.created_at,
        midi_file_count=midi_counts.get(track.id, 0),
    )


def _linked_session(entry: LinkedSessionEntry) -> MarketLinkedSession:
    return MarketLinkedSession(
        session_id=entry.session_id,
        session_code=entry.session_code,
        track_title=entry.track_title,
        artist=entry.artist,
        state=entry.state,
    )


def _midi_file_summary(midi_file, linked_sessions: list[LinkedSessionEntry]) -> MarketMidiFileSummary:
    return MarketMidiFileSummary(
        id=midi_file.id,
        relative_path=midi_file.relative_path,
        indexed_at=midi_file.indexed_at,
        linked_sessions=[_linked_session(entry) for entry in linked_sessions],
    )


@dataclass
class ListMarketArtistsUseCase:
    """Listagem paginada/buscável de `market_artists`, pra tela de catálogo."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, *, query: Optional[str], page: int, page_size: int) -> MarketArtistListResponse:
        repo = self._repository or MarketMidiRepository()
        rows, total = repo.list_artists_page(query=query, page=page, page_size=page_size)
        track_counts = repo.count_tracks_by_artist([row.id for row in rows])
        items = [_artist_summary(row, track_counts) for row in rows]
        return MarketArtistListResponse(items=items, page=page, page_size=page_size, total=total)


@dataclass
class GetMarketArtistUseCase:
    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, artist_id: int) -> Optional[MarketArtistDetail]:
        repo = self._repository or MarketMidiRepository()
        artist = repo.get_artist(artist_id)
        if artist is None:
            return None

        track_ids = [track.id for track in artist.tracks]
        midi_counts = repo.count_midi_files_by_track(track_ids)
        tracks = [_track_summary(track, artist, midi_counts) for track in artist.tracks]
        return MarketArtistDetail(
            id=artist.id,
            name=artist.name,
            source=artist.source,
            created_at=artist.created_at,
            tracks=tracks,
        )


@dataclass
class UpdateMarketArtistUseCase:
    """Renomeia um artista — recalcula `name_norm` pra manter o fuzzy match
    (ver ResolveArtistCandidatesUseCase) consistente com o novo nome."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, artist_id: int, payload: MarketArtistUpdate) -> Optional[MarketArtistDetail]:
        from app.services.market_midi_matcher import normalize_artist

        repo = self._repository or MarketMidiRepository()
        name = payload.name.strip()
        updated = repo.rename_artist(artist_id, name=name, name_norm=normalize_artist(name))
        if not updated:
            return None

        return GetMarketArtistUseCase(self._job_service, repo).execute(artist_id)


@dataclass
class DeleteMarketArtistUseCase:
    """Exclui um artista — cascade do ORM (`cascade=\"all, delete-orphan\"`) apaga
    junto as músicas e os arquivos MIDI dele."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, artist_id: int) -> bool:
        repo = self._repository or MarketMidiRepository()
        return repo.delete_artist(artist_id)


@dataclass
class ListMarketTracksUseCase:
    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(
        self, *, artist_id: Optional[int], query: Optional[str], page: int, page_size: int
    ) -> MarketTrackListResponse:
        repo = self._repository or MarketMidiRepository()
        rows, total = repo.list_tracks_page(artist_id=artist_id, query=query, page=page, page_size=page_size)
        midi_counts = repo.count_midi_files_by_track([track.id for track, _artist in rows])
        items = [_track_summary(track, artist, midi_counts) for track, artist in rows]
        return MarketTrackListResponse(items=items, page=page, page_size=page_size, total=total)


@dataclass
class GetMarketTrackUseCase:
    _job_service: object
    _repository: Optional[MarketMidiRepository] = None
    _identity_repository: Optional[SessionMusicIdentityRepository] = None

    def execute(self, track_id: int) -> Optional[MarketTrackDetail]:
        repo = self._repository or MarketMidiRepository()
        track = repo.get_track(track_id)
        if track is None:
            return None

        identity_repo = self._identity_repository or SessionMusicIdentityRepository()
        linked_by_file = identity_repo.list_sessions_for_midi_files([f.id for f in track.midi_files])
        midi_files = [
            _midi_file_summary(midi_file, linked_by_file.get(midi_file.id, [])) for midi_file in track.midi_files
        ]
        return MarketTrackDetail(
            id=track.id,
            artist_id=track.artist_id,
            artist_name=track.artist.name,
            title=track.title,
            source=track.source,
            created_at=track.created_at,
            midi_files=midi_files,
        )


@dataclass
class UpdateMarketTrackUseCase:
    """Renomeia a música e/ou reatribui pra outro artista — recalcula
    `title_norm` (mesma lógica de normalização usada no matching de mercado)
    quando o título muda."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None
    _identity_repository: Optional[SessionMusicIdentityRepository] = None

    def execute(self, track_id: int, payload: MarketTrackUpdate) -> Optional[MarketTrackDetail]:
        from app.services.market_midi_matcher import normalize_title

        repo = self._repository or MarketMidiRepository()
        title = payload.title.strip() if payload.title else None
        title_norm = normalize_title(title) if title else None
        updated = repo.update_track(track_id, title=title, title_norm=title_norm, artist_id=payload.artist_id)
        if not updated:
            return None

        return GetMarketTrackUseCase(self._job_service, repo, self._identity_repository).execute(track_id)


@dataclass
class DeleteMarketTrackUseCase:
    """Exclui uma música — cascade do ORM apaga junto os arquivos MIDI dela."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, track_id: int) -> bool:
        repo = self._repository or MarketMidiRepository()
        return repo.delete_track(track_id)


@dataclass
class DeleteMarketMidiFileUseCase:
    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, file_id: int) -> bool:
        repo = self._repository or MarketMidiRepository()
        return repo.delete_midi_file(file_id)

from dataclasses import dataclass
from typing import Optional

from app.models import MusicIdentity, MusicIdentityRequest
from app.repositories.market_midi_repository import MarketMidiRepository
from app.repositories.session_music_identity_repository import SessionMusicIdentityRepository


@dataclass
class SaveMusicIdentityUseCase:
    """Persiste a identidade musical confirmada pelo usuário no step 3 do
    wizard. Se nenhum `artist_id` foi escolhido no preview, resolve o texto
    digitado contra o catálogo (match exato por nome normalizado) e cria um
    artista novo (`source='user_created'`) se não existir — a sessão nunca
    fica sem `artist_id` depois desse passo."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None
    _identity_repository: Optional[SessionMusicIdentityRepository] = None

    def execute(self, session_id: str, payload: MusicIdentityRequest) -> MusicIdentity:
        from app.services.market_midi_matcher import normalize_artist

        repo = self._repository or MarketMidiRepository()
        identity_repo = self._identity_repository or SessionMusicIdentityRepository()

        artist_id = payload.artist_id
        if artist_id is None:
            artist_id = repo.get_or_create_artist(
                payload.artist_text, normalize_artist(payload.artist_text), source="user_created"
            )

        identity_repo.upsert(
            session_id,
            artist_id=artist_id,
            artist_text=payload.artist_text,
            title_text=payload.title_text,
            source_url=payload.source_url,
        )

        saved = identity_repo.get(session_id)
        return MusicIdentity(
            session_id=session_id,
            artist_id=saved.artist_id,
            artist_text=saved.artist_text,
            title_text=saved.title_text,
            source_url=saved.source_url,
            track_id=saved.track_id,
            resolved_midi_file_id=saved.resolved_midi_file_id,
            resolved_at=saved.resolved_at,
        )

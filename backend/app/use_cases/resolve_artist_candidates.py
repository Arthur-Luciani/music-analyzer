from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from app.models import ArtistCandidate
from app.repositories.market_midi_repository import MarketMidiRepository

# Mesmo piso usado no prefiltro de artista do matching de mercado
# (market_midi_matcher.ARTIST_PREFILTER_THRESHOLD) — "vale a pena sugerir",
# não "é com certeza esse artista" (essa decisão fica com o usuário no step 3).
SUGGESTION_THRESHOLD = 55.0


@dataclass
class ResolveArtistCandidatesUseCase:
    """Fuzzy match só de texto contra `market_artists`, pro preview ao vivo
    do step 3 do wizard de criação de sessão. Sem DTW/áudio — é só uma
    sugestão, não uma confirmação (ver SaveMusicIdentityUseCase)."""

    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    def execute(self, query: str, *, limit: int = 5) -> list[ArtistCandidate]:
        from app.services.market_midi_matcher import normalize_artist

        query_norm = normalize_artist(query)
        if not query_norm:
            return []

        repo = self._repository or MarketMidiRepository()
        artists = repo.list_all_artists()

        scored = [
            ArtistCandidate(id=artist.id, name=artist.name, score=fuzz.token_sort_ratio(query_norm, artist.name_norm))
            for artist in artists
        ]
        scored = [candidate for candidate in scored if candidate.score >= SUGGESTION_THRESHOLD]
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:limit]

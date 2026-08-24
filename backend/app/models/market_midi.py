from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


MarketMidiStatus = Literal[
    "not_indexed",         # dataset ainda não foi baixado/indexado (setup_market_midi.py)
    "no_match",            # índice presente, mas nenhum candidato passou o threshold de matching
    "low_confidence",      # candidato encontrado, mas o alinhamento DTW não passou no gate de qualidade
    "candidate_unreadable",  # candidato encontrado, mas o arquivo MIDI está corrompido/sem trilha de bateria
    "applied",             # candidato encontrado, alinhado com confiança e aplicado como drum_transcription.mid
]


class MarketMidiMatchResult(BaseModel):
    """Resultado da tentativa de casar/alinhar um MIDI de mercado para a sessão."""
    status: MarketMidiStatus
    matched_artist: Optional[str] = None
    matched_title: Optional[str] = None
    match_score: Optional[float] = None
    alignment_cost: Optional[float] = None
    alignment_coverage: Optional[float] = None
    applied: bool = False
    checked_at: datetime


class MarketLinkedSession(BaseModel):
    """Uma sessão real que já usou este arquivo MIDI como transcrição
    vencedora (`session_music_identity.resolved_midi_file_id`)."""
    session_id: str
    session_code: str
    track_title: Optional[str] = None
    artist: Optional[str] = None
    state: str


class MarketMidiFileSummary(BaseModel):
    """Um arquivo MIDI candidato, pra tela de catálogo (view/edit)."""
    id: int
    relative_path: str
    indexed_at: datetime
    linked_sessions: List[MarketLinkedSession] = Field(default_factory=list)


class MarketTrackSummary(BaseModel):
    """Uma música do catálogo, com o artista já resolvido pro nome (evita
    round-trip extra na tela de listagem de músicas)."""
    id: int
    artist_id: int
    artist_name: str
    title: str
    source: str
    created_at: datetime
    midi_file_count: int


class MarketTrackDetail(BaseModel):
    id: int
    artist_id: int
    artist_name: str
    title: str
    source: str
    created_at: datetime
    midi_files: List[MarketMidiFileSummary] = Field(default_factory=list)


class MarketArtistSummary(BaseModel):
    id: int
    name: str
    source: str
    created_at: datetime
    track_count: int


class MarketArtistDetail(BaseModel):
    id: int
    name: str
    source: str
    created_at: datetime
    tracks: List[MarketTrackSummary] = Field(default_factory=list)


class MarketArtistListResponse(BaseModel):
    items: List[MarketArtistSummary]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class MarketTrackListResponse(BaseModel):
    items: List[MarketTrackSummary]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class MarketArtistUpdate(BaseModel):
    name: str = Field(..., min_length=1)


class MarketTrackUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    artist_id: Optional[int] = None

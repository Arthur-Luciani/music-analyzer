from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


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

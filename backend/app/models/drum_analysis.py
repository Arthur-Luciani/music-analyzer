from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DrumHit(BaseModel):
    """Representa um golpe individual de bateria."""
    time: float               # segundos desde o início
    type: str                 # kick | snare | hihat | tom | cymbal
    velocity: float = Field(ge=0.0, le=1.0)  # intensidade do golpe
    confidence: float = 0.0                  # probabilidade do modelo


class DrumAnalysis(BaseModel):
    """Resultado completo da análise do stem de bateria."""
    bpm: float                         # BPM global estimado
    time_signature: str = "4/4"        # compasso estimado
    duration_seconds: float            # duração total
    beat_count: int                    # total de beats detectados
    beats: list[float]                 # timestamps de cada beat [0.0, 0.5, 1.0, ...]
    hits: list[DrumHit] = []           # golpes detectados (populado na Fase 3)
    analysis_version: str = "1.0"
    analyzed_at: datetime
    status: str = "partial"            # partial | complete
    is_corrected: bool = False         # indica se foi editado manualmente pelo usuário


class DrumCorrections(BaseModel):
    """Payload para salvar correções manuais do usuário."""
    hits: list[DrumHit]
    corrected_at: datetime = Field(default_factory=datetime.utcnow)

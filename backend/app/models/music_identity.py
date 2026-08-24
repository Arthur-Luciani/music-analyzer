from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ArtistCandidate(BaseModel):
    """Sugestão de artista do catálogo pro preview ao vivo do step 3 do wizard."""
    id: int
    name: str
    score: float


class MusicIdentityRequest(BaseModel):
    artist_text: str = Field(..., min_length=1)
    title_text: str = Field(..., min_length=1)
    artist_id: Optional[int] = Field(
        default=None,
        description="ID de um ArtistCandidate escolhido no preview; se omitido, resolve por texto (get-or-create)",
    )
    source_url: Optional[str] = None


class MusicIdentity(BaseModel):
    session_id: str
    artist_id: Optional[int] = None
    artist_text: str
    title_text: str
    source_url: Optional[str] = None
    track_id: Optional[int] = None
    resolved_midi_file_id: Optional[int] = None
    resolved_at: Optional[datetime] = None

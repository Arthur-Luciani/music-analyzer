from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.common import ALLOWED_STEMS, JobState, MasterMetrics
from app.models.search import SearchCandidate

class ProcessRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Search term or video URL")
    selected_source_id: Optional[str] = Field(
        default=None,
        description="Source identifier selected by user from search results",
    )
    target_stems: Optional[List[str]] = Field(
        default=None,
        description="Optional stems to return: vocals, drums, bass, other",
    )

    @field_validator("target_stems")
    @classmethod
    def validate_target_stems(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None

        normalized = [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]
        if not normalized:
            return None

        invalid = [item for item in normalized if item not in ALLOWED_STEMS]
        if invalid:
            invalid_values = ", ".join(sorted(set(invalid)))
            raise ValueError(f"Invalid stem names: {invalid_values}")

        seen: set[str] = set()
        deduped: List[str] = []
        for stem_name in normalized:
            if stem_name not in seen:
                deduped.append(stem_name)
                seen.add(stem_name)

        return deduped


class ProcessResponse(BaseModel):
    job_id: str
    session_id: Optional[str] = None
    session_code: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    session_id: str
    session_code: str
    query: str
    selected_track: Optional[SearchCandidate] = None
    target_stems: List[str] = Field(default_factory=lambda: ALLOWED_STEMS.copy())
    state: JobState
    progress: int = Field(ge=0, le=100)
    message: str
    created_at: datetime
    updated_at: datetime
    stems: Optional[Dict[str, str]] = None
    error: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = Field(default=None, ge=0)
    separation_device: Optional[str] = None
    master_metrics: Optional[MasterMetrics] = None

    @staticmethod
    def resolve_target_stems(requested: Optional[List[str]]) -> List[str]:
        if requested is None:
            return ALLOWED_STEMS.copy()

        normalized = [stem_name.strip().lower() for stem_name in requested if stem_name and stem_name.strip()]
        if not normalized:
            return ALLOWED_STEMS.copy()

        seen: set[str] = set()
        filtered: List[str] = []
        for stem_name in normalized:
            if stem_name in ALLOWED_STEMS and stem_name not in seen:
                filtered.append(stem_name)
                seen.add(stem_name)

        if not filtered:
            return ALLOWED_STEMS.copy()

        return filtered

    def calculate_eta(self, now: datetime) -> Optional[int]:
        if self.state in {JobState.ready, JobState.failed}:
            return 0
        if self.progress <= 0:
            return None

        elapsed_seconds = max(1.0, (now - self.created_at).total_seconds())
        remaining_progress = max(0, 100 - self.progress)
        estimate = round((elapsed_seconds * remaining_progress) / max(self.progress, 1))
        return max(0, min(int(estimate), 21600))


class SessionSummary(BaseModel):
    session_id: str
    job_id: str
    session_code: str
    track_title: Optional[str] = None
    artist: Optional[str] = None
    identity_artist: Optional[str] = Field(
        default=None, description="Artista confirmado no wizard (session_music_identity), quando existir"
    )
    identity_title: Optional[str] = Field(
        default=None, description="Título confirmado no wizard (session_music_identity), quando existir"
    )
    status: JobState
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionSummary):
    query: str
    selected_track: Optional[SearchCandidate] = None
    target_stems: List[str] = Field(default_factory=lambda: ALLOWED_STEMS.copy())
    progress: int = Field(ge=0, le=100)
    message: str
    stems: Optional[Dict[str, str]] = None
    error: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = Field(default=None, ge=0)
    separation_device: Optional[str] = None
    master_metrics: Optional[MasterMetrics] = None


class SessionListResponse(BaseModel):
    items: List[SessionSummary]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class SessionEvent(BaseModel):
    timestamp: datetime
    stage: str
    level: str
    message: str
    progress: int = Field(ge=0, le=100)

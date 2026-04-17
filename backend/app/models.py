from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobState(str, Enum):
    queued = "queued"
    downloading = "downloading"
    separating = "separating"
    ready = "ready"
    failed = "failed"


class ProcessRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Artist + song title")
    selected_source_id: Optional[str] = Field(
        default=None,
        description="Source identifier selected by user when query is ambiguous",
    )


class ProcessResponse(BaseModel):
    job_id: str


class ScoreBreakdown(BaseModel):
    title: int = Field(ge=0, le=100)
    artist: int = Field(ge=0, le=100)
    duration: int = Field(ge=0, le=100)
    quality: int = Field(ge=0, le=100)
    penalties: int = Field(ge=0, le=100)


class SearchCandidate(BaseModel):
    source_id: str
    source: str
    title: str
    artist: str
    duration_seconds: int = Field(ge=1)
    url: str
    score: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown


class SearchResponse(BaseModel):
    query: str
    candidates: List[SearchCandidate]
    recommended_source_id: Optional[str] = None
    requires_selection: bool = False


class JobStatus(BaseModel):
    job_id: str
    query: str
    selected_track: Optional[SearchCandidate] = None
    state: JobState
    progress: int = Field(ge=0, le=100)
    message: str
    created_at: datetime
    updated_at: datetime
    stems: Optional[Dict[str, str]] = None
    error: Optional[str] = None

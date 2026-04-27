from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_STEMS = ["vocals", "drums", "bass", "other"]


class JobState(str, Enum):
    queued = "queued"
    downloading = "downloading"
    separating = "separating"
    ready = "ready"
    failed = "failed"


class ExportState(str, Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


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


class SearchCandidate(BaseModel):
    source_id: str
    source: str
    title: str
    artist: str
    duration_seconds: int = Field(ge=1)
    url: str
    compatibility_score: Optional[int] = Field(default=None, ge=0, le=100)
    compatibility_breakdown: Optional[Dict[str, int]] = None


class SearchResponse(BaseModel):
    query: str
    candidates: List[SearchCandidate]
    recommended_source_id: Optional[str] = None


class MasterMetrics(BaseModel):
    lufs: float
    true_peak_dbtp: float
    headroom_db: float = Field(ge=0)


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


class SessionSummary(BaseModel):
    session_id: str
    session_code: str
    track_title: Optional[str] = None
    artist: Optional[str] = None
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


class StemMixState(BaseModel):
    gain: float = Field(default=0.0, ge=-60.0, le=24.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    mute: bool = False
    solo: bool = False
    send_fx: float = Field(default=0.0, ge=0.0, le=1.0)


class MixStateUpdate(BaseModel):
    per_stem: Dict[str, StemMixState] = Field(default_factory=dict)
    master_gain: Optional[float] = Field(default=None, ge=-60.0, le=24.0)

    @field_validator("per_stem")
    @classmethod
    def validate_per_stem(cls, value: Dict[str, StemMixState]) -> Dict[str, StemMixState]:
        normalized: Dict[str, StemMixState] = {}
        for stem_name, stem_state in value.items():
            key = str(stem_name).strip().lower()
            if key in ALLOWED_STEMS:
                normalized[key] = stem_state
        return normalized


class MixState(BaseModel):
    per_stem: Dict[str, StemMixState]
    master_gain: float = Field(ge=-60.0, le=24.0)
    updated_at: datetime


class ExportRequest(BaseModel):
    preset: str = Field(default="study_mix", description="study_mix, stems, custom")
    format: str = Field(default="wav", description="wav or zip")
    options: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("preset")
    @classmethod
    def validate_preset(cls, value: str) -> str:
        normalized = (value or "study_mix").strip().lower()
        if normalized not in {"study_mix", "stems", "custom"}:
            raise ValueError("Invalid preset")
        return normalized

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = (value or "wav").strip().lower()
        if normalized not in {"wav", "zip"}:
            raise ValueError("Invalid format")
        return normalized


class ExportArtifact(BaseModel):
    kind: str
    file_name: str
    path: str
    size_bytes: int = Field(ge=0)
    download_url: str


class ExportJob(BaseModel):
    export_id: str
    session_id: str
    preset: str
    format: str
    state: ExportState
    progress: int = Field(ge=0, le=100)
    output_files: List[ExportArtifact] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SessionEvent(BaseModel):
    timestamp: datetime
    stage: str
    level: str
    message: str
    progress: int = Field(ge=0, le=100)

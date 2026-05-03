from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.common import ExportState


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

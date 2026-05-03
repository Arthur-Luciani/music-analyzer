from enum import Enum
from pydantic import BaseModel, Field

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

class MasterMetrics(BaseModel):
    lufs: float
    true_peak_dbtp: float
    headroom_db: float = Field(ge=0)

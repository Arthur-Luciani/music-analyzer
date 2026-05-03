from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.common import ALLOWED_STEMS

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

    def apply_update(self, update: MixStateUpdate) -> "MixState":
        merged_per_stem = {**self.per_stem, **update.per_stem}
        next_master_gain = self.master_gain if update.master_gain is None else update.master_gain

        return MixState(
            per_stem=merged_per_stem,
            master_gain=next_master_gain,
            updated_at=datetime.utcnow(),
        )

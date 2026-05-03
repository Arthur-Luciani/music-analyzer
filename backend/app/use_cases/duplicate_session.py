from dataclasses import dataclass
from typing import Optional

from app.models import JobStatus

@dataclass
class DuplicateSessionUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[JobStatus]:
        source_job = await self._job_service.get_job(session_id)
        if source_job is None:
            return None

        if source_job.selected_track is None:
            raise ValueError("Selected source is unavailable for this session")

        return await self._job_service.create_job(
            source_job.query,
            selected_track=source_job.selected_track,
            target_stems=source_job.target_stems,
        )

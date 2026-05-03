import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from app.models import JobStatus, JobState, SearchCandidate
from app.settings import settings

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")
logger = logging.getLogger(__name__)


@dataclass
class CreateSessionUseCase:
    _job_service: object

    async def execute(
        self,
        query: str,
        selected_track: Optional[SearchCandidate] = None,
        target_stems: Optional[list[str]] = None,
    ) -> JobStatus:
        now = datetime.utcnow()
        session_id = str(uuid4())
        resolved_target_stems = JobStatus.resolve_target_stems(target_stems)
        session_code = await asyncio.to_thread(
            self._job_service._store.create_session,
            session_id=session_id,
            query=query,
            selected_track=selected_track,
            target_stems=resolved_target_stems,
            state=JobState.queued,
            progress=0,
            message="Job queued",
            created_at=now,
            updated_at=now,
        )

        job = JobStatus(
            job_id=session_id,
            session_id=session_id,
            session_code=session_code,
            query=query,
            selected_track=selected_track,
            target_stems=resolved_target_stems,
            state=JobState.queued,
            progress=0,
            message="Job queued",
            created_at=now,
            updated_at=now,
        )
        async with self._job_service._lock:
            self._job_service._jobs[job.job_id] = job
            self._job_service._subscribers[job.job_id] = set()

        try:
            await self._job_service.add_session_event(
                job.session_id,
                stage=job.state.value,
                level="info",
                message=job.message,
                progress=job.progress,
            )
        except Exception as exc:
            logger.warning("Failed to persist initial event for %s: %s", job.session_id, exc)
        return job

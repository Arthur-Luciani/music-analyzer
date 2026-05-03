from dataclasses import dataclass
from typing import Optional

from app.models import JobStatus, JobState


@dataclass
class ReprocessSessionUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[JobStatus]:
        source_job = await self._job_service.get_job(session_id)
        if source_job is None:
            return None

        if source_job.selected_track is None:
            raise ValueError("Selected source is unavailable for this session")

        # Em vez de criar um novo job (duplicar), resetamos o estado do atual
        # e limpamos resultados anteriores para forçar novo processamento real.
        await self._job_service.clear_session_data(session_id)
        
        return await self._job_service.update_job(
            session_id,
            state=JobState.queued,
            progress=0,
            message="Reiniciando processamento da sessão...",
            stems={},
            master_metrics=None,
            error=None
        )

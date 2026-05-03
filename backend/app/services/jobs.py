import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.models import (
    ExportArtifact,
    ExportJob,
    ExportState,
    JobState,
    JobStatus,
    MasterMetrics,
    MixState,
    MixStateUpdate,
    SearchCandidate,
    SearchResponse,
    SessionEvent,
    SessionSummary,
    StemMixState,
    DrumAnalysis,
    DrumCorrections,
)
from app.repositories.session_repository import SessionRepository

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")
logger = logging.getLogger(__name__)


class JobService:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobStatus] = {}
        self._export_jobs: Dict[str, ExportJob] = {}
        self._subscribers: Dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._store = SessionRepository()
        
        # Injetando casos de uso
        try:
            from app.use_cases import (
                SearchCandidatesUseCase,
                CreateSessionUseCase,
                ProcessSessionUseCase,
                DuplicateSessionUseCase,
                ReprocessSessionUseCase,
                GetMixStateUseCase,
                SaveMixStateUseCase,
                CreateExportUseCase,
                RunExportUseCase,
                AnalyzeDrumStemUseCase,
                SaveDrumCorrectionsUseCase,
            )

            self._search_use_case = SearchCandidatesUseCase(self)
            self._create_session_use_case = CreateSessionUseCase(self)
            self._process_session_use_case = ProcessSessionUseCase(self)
            self._duplicate_session_use_case = DuplicateSessionUseCase(self)
            self._reprocess_session_use_case = ReprocessSessionUseCase(self)
            self._get_mix_state_use_case = GetMixStateUseCase(self)
            self._save_mix_state_use_case = SaveMixStateUseCase(self)
            self._create_export_use_case = CreateExportUseCase(self)
            self._run_export_use_case = RunExportUseCase(self)
            self._analyze_drum_use_case = AnalyzeDrumStemUseCase(self)
            self._save_drum_corrections_use_case = SaveDrumCorrectionsUseCase(self)
        except Exception as e:
            logger.error(f"Failed to load use cases: {e}")

    def search_candidates(self, query: str, *, limit: int = 5) -> SearchResponse:
        return self._search_use_case.execute(query, limit=limit)

    def find_candidate(self, query: str, source_id: str) -> Optional[SearchCandidate]:
        return self._search_use_case.find_candidate(query, source_id)

    async def create_job(
        self,
        query: str,
        selected_track: Optional[SearchCandidate] = None,
        target_stems: Optional[list[str]] = None,
    ) -> JobStatus:
        return await self._create_session_use_case.execute(query, selected_track=selected_track, target_stems=target_stems)

    async def get_job(self, job_id: str) -> Optional[JobStatus]:
        async with self._lock:
            cached = self._jobs.get(job_id)
            if cached is not None:
                return cached

        persisted = await asyncio.to_thread(self._store.get_session, job_id)
        if persisted is None:
            return None

        async with self._lock:
            self._jobs[job_id] = persisted

        return persisted

    async def list_sessions(
        self,
        *,
        query: Optional[str],
        status: Optional[JobState],
        created_from: Optional[datetime],
        created_to: Optional[datetime],
        page: int,
        page_size: int,
    ) -> tuple[list[SessionSummary], int]:
        persisted_jobs, total = await asyncio.to_thread(
            self._store.list_sessions,
            query=query,
            status=status,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )

        summaries = [
            SessionSummary(
                session_id=job.session_id,
                job_id=job.job_id,
                session_code=job.session_code,
                track_title=job.selected_track.title if job.selected_track else None,
                artist=job.selected_track.artist if job.selected_track else None,
                status=job.state,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in persisted_jobs
        ]
        return summaries, total

    @staticmethod
    def _default_mix_state() -> MixState:
        return MixState(
            per_stem={stem_name: StemMixState() for stem_name in SUPPORTED_STEMS},
            master_gain=0.0,
            updated_at=datetime.utcnow(),
        )

    async def get_mix_state(self, session_id: str) -> Optional[MixState]:
        return await self._get_mix_state_use_case.execute(session_id)

    async def save_mix_state(self, session_id: str, update: MixStateUpdate) -> Optional[MixState]:
        return await self._save_mix_state_use_case.execute(session_id, update)

    async def add_session_event(
        self,
        session_id: str,
        *,
        stage: str,
        level: str,
        message: str,
        progress: int,
    ) -> None:
        await asyncio.to_thread(
            self._store.append_session_event,
            session_id=session_id,
            timestamp=datetime.utcnow(),
            stage=stage,
            level=level,
            progress=max(0, min(100, progress)),
            message=message,
        )

    async def list_session_events(self, session_id: str) -> Optional[list[SessionEvent]]:
        session = await self.get_job(session_id)
        if session is None:
            return None
        return await asyncio.to_thread(self._store.list_session_events, session_id)

    @staticmethod
    def _build_export_download_url(session_id: str, export_id: str, file_name: str) -> str:
        return f"/api/sessions/{session_id}/exports/{export_id}/files/{file_name}"

    async def create_export_job(self, session_id: str, preset: str, format_name: str) -> Optional[ExportJob]:
        return await self._create_export_use_case.execute(session_id, preset, format_name)

    async def get_export_job(self, session_id: str, export_id: str) -> Optional[ExportJob]:
        async with self._lock:
            cached = self._export_jobs.get(export_id)
            if cached is not None and cached.session_id == session_id:
                return cached

        persisted = await asyncio.to_thread(self._store.get_export_job, session_id, export_id)
        if persisted is None:
            return None

        async with self._lock:
            self._export_jobs[export_id] = persisted

        return persisted

    async def list_export_jobs(self, session_id: str) -> Optional[list[ExportJob]]:
        session = await self.get_job(session_id)
        if session is None:
            return None

        jobs = await asyncio.to_thread(self._store.list_export_jobs, session_id)
        async with self._lock:
            for export_job in jobs:
                self._export_jobs[export_job.export_id] = export_job

        return jobs

    async def update_export_job(
        self,
        session_id: str,
        export_id: str,
        *,
        state: ExportState,
        progress: int,
        output_files: Optional[list[ExportArtifact]] = None,
        error: Optional[str] = None,
    ) -> Optional[ExportJob]:
        existing = await self.get_export_job(session_id, export_id)
        if existing is None:
            return None

        updated = existing.model_copy(
            update={
                "state": state,
                "progress": progress,
                "output_files": output_files if output_files is not None else existing.output_files,
                "error": error,
                "updated_at": datetime.utcnow(),
            }
        )

        async with self._lock:
            self._export_jobs[export_id] = updated

        await asyncio.to_thread(self._store.save_export_job, updated)

        level = "error" if state == ExportState.failed else "info"
        try:
            await self.add_session_event(
                session_id,
                stage=f"export:{state.value}",
                level=level,
                message=error or f"Export {state.value}",
                progress=progress,
            )
        except Exception as exc:
            logger.warning("Failed to persist export event for %s/%s: %s", session_id, export_id, exc)
        return updated

    async def get_export_file_path(self, session_id: str, export_id: str, file_name: str) -> Optional[Path]:
        export_job = await self.get_export_job(session_id, export_id)
        if export_job is None:
            return None

        for artifact in export_job.output_files:
            if artifact.file_name != file_name:
                continue

            requested_file = Path(artifact.path).resolve()
            
            # Simple check since storage_root might not be imported directly here anymore
            if requested_file.is_file():
                return requested_file

        return None

    async def run_export_pipeline(self, session_id: str, export_id: str, options: Optional[dict[str, object]] = None) -> None:
        return await self._run_export_use_case.execute(session_id, export_id, options)

    async def duplicate_session(self, session_id: str) -> Optional[JobStatus]:
        return await self._duplicate_session_use_case.execute(session_id)

    async def reprocess_session(self, session_id: str) -> Optional[JobStatus]:
        return await self._reprocess_session_use_case.execute(session_id)

    async def analyze_drum_stem(self, session_id: str) -> Optional[DrumAnalysis]:
        return await self._analyze_drum_use_case.execute(session_id)

    async def get_drum_analysis(self, session_id: str) -> Optional[DrumAnalysis]:
        from app.use_cases import AnalyzeDrumStemUseCase
        return AnalyzeDrumStemUseCase.load_saved_analysis(session_id)

    async def save_drum_corrections(self, session_id: str, corrections: DrumCorrections) -> Optional[DrumAnalysis]:
        return await self._save_drum_corrections_use_case.execute(session_id, corrections)

    async def clear_session_data(self, session_id: str) -> None:
        """Clears associated data (events, exports, stems) but keeps the session."""
        await asyncio.to_thread(self._store.clear_session_data, session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session, its data and stems from disk.

        Evicts from the in-memory cache first, then delegates to the repository.
        Returns True if the session was found and deleted.
        """
        async with self._lock:
            self._jobs.pop(session_id, None)
            # Also remove any cached export jobs for this session
            self._export_jobs = {
                eid: ej for eid, ej in self._export_jobs.items()
                if ej.session_id != session_id
            }

        return await asyncio.to_thread(self._store.delete_session, session_id)

    async def cleanup_stale_sessions(self, older_than: datetime) -> int:
        """Deletes sessions that have not been updated since `older_than`."""
        stale_sessions, _ = await self.list_sessions(
            query=None,
            status=None,
            created_from=None,
            created_to=None,
            page=1,
            page_size=10000,
        )
        deleted_count = 0
        for job in stale_sessions:
            if job.updated_at < older_than:
                if await self.delete_session(job.session_id):
                    deleted_count += 1
        return deleted_count

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(job_id)
            if subscribers is not None and queue in subscribers:
                subscribers.remove(queue)

    async def _broadcast(self, job_id: str, payload: dict) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(job_id, set()))
        for queue in subscribers:
            await queue.put(payload)

    async def update_job(
        self,
        job_id: str,
        *,
        state: JobState,
        progress: int,
        message: str,
        stems: Optional[Dict[str, str]] = None,
        error: Optional[str] = None,
        estimated_remaining_seconds: Optional[int] = None,
        separation_device: Optional[str] = None,
        master_metrics: Optional[MasterMetrics] = None,
    ) -> Optional[JobStatus]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            now = datetime.utcnow()
            if estimated_remaining_seconds is None:
                estimated_remaining_seconds = job.calculate_eta(now)

            updated = job.model_copy(
                update={
                    "state": state,
                    "progress": progress,
                    "message": message,
                    "updated_at": now,
                    "stems": stems if stems is not None else job.stems,
                    "error": error,
                    "estimated_remaining_seconds": estimated_remaining_seconds,
                    "separation_device": separation_device or job.separation_device,
                    "master_metrics": master_metrics if master_metrics is not None else job.master_metrics,
                }
            )
            self._jobs[job_id] = updated

        try:
            await asyncio.to_thread(self._store.save_session, updated)
        except Exception as exc:
            logger.warning("Failed to persist session update for %s: %s", job_id, exc)

        level = "error" if state == JobState.failed else "info"
        try:
            await self.add_session_event(
                updated.session_id,
                stage=state.value,
                level=level,
                message=error or message,
                progress=progress,
            )
        except Exception as exc:
            logger.warning("Failed to persist session event for %s: %s", updated.session_id, exc)

        await self._broadcast(job_id, updated.model_dump(mode="json"))
        return updated


    async def run_pipeline(self, job_id: str) -> None:
        await self._process_session_use_case.execute(job_id)
        
        # Disparar análise de bateria automaticamente se o stem estiver presente
        job = await self.get_job(job_id)
        if job and job.state == JobState.ready and job.stems and "drums" in job.stems:
            logger.info(f"Triggering automatic drum analysis for {job_id}")
            # Usamos create_task para que a análise rode em background sem travar o fim do pipeline principal
            asyncio.create_task(self.analyze_drum_stem(job_id))

job_service = JobService()

import asyncio
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.models import ExportArtifact, ExportJob, ExportState, JobState, JobStatus, MasterMetrics, MixState, MixStateUpdate, SearchCandidate, SearchResponse, SessionEvent, SessionSummary, StemMixState
from app.repositories.session_store import SQLiteSessionStore
from app.settings import settings

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")
logger = logging.getLogger(__name__)


class JobService:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobStatus] = {}
        self._export_jobs: Dict[str, ExportJob] = {}
        self._subscribers: Dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._recent_searches: Dict[str, list[SearchCandidate]] = {}
        self._store = SQLiteSessionStore(settings.sessions_db_path)

    def search_candidates(self, query: str, *, limit: int = 5) -> SearchResponse:
        query_key = self._cache_query_key(query)
        if not query_key:
            return SearchResponse(query=query, candidates=[], recommended_source_id=None)

        entries = self._search_youtube(query, limit=max(1, min(limit, 10)))
        candidates = [
            candidate
            for index, entry in enumerate(entries, start=1)
            if (candidate := self._entry_to_candidate(entry, index, query)) is not None
        ]

        self._recent_searches[query_key] = candidates
        recommended_source_id = candidates[0].source_id if candidates else None
        return SearchResponse(
            query=query,
            candidates=candidates,
            recommended_source_id=recommended_source_id,
        )

    def find_candidate(self, query: str, source_id: str) -> Optional[SearchCandidate]:
        query_key = self._cache_query_key(query)
        cached = self._recent_searches.get(query_key, [])
        for candidate in cached:
            if candidate.source_id == source_id:
                return candidate

        response = self.search_candidates(query, limit=10)
        for candidate in response.candidates:
            if candidate.source_id == source_id:
                return candidate
        return None

    def _search_youtube(self, query: str, *, limit: int) -> list[dict[str, object]]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": True,
            "default_search": "ytsearch",
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                if self._looks_like_url(query):
                    result = ydl.extract_info(query, download=False)
                else:
                    result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except DownloadError:
            return []
        except Exception:
            return []

        if not isinstance(result, dict):
            return []

        if isinstance(result.get("entries"), list):
            entries = [entry for entry in result["entries"] if isinstance(entry, dict)]
        else:
            entries = [result]

        return entries

    def _entry_to_candidate(
        self,
        entry: dict[str, object],
        position: int,
        query: str,
    ) -> Optional[SearchCandidate]:
        title = str(entry.get("title") or "").strip()
        if not title:
            return None

        video_id = str(entry.get("id") or "").strip()
        artist = str(entry.get("uploader") or entry.get("channel") or "Unknown").strip()
        source = str(entry.get("extractor_key") or "youtube").lower()

        duration_raw = entry.get("duration")
        duration_seconds = int(duration_raw) if isinstance(duration_raw, (int, float)) and duration_raw > 0 else 1

        url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not url:
            return None

        source_id = f"yt_{video_id}" if video_id else f"yt_result_{position}"
        compatibility_score, compatibility_breakdown = self._estimate_compatibility_score(query, title, artist)

        return SearchCandidate(
            source_id=source_id,
            source=source,
            title=title,
            artist=artist,
            duration_seconds=duration_seconds,
            url=url,
            compatibility_score=compatibility_score,
            compatibility_breakdown=compatibility_breakdown,
        )

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        return bool(re.match(r"^https?://", value.strip(), flags=re.IGNORECASE))

    @staticmethod
    def _cache_query_key(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _normalize_for_score(value: str) -> list[str]:
        lowered = (value or "").strip().lower()
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
        return [token for token in cleaned.split() if token]

    @staticmethod
    def _token_overlap_score(query_tokens: list[str], candidate_tokens: list[str]) -> int:
        if not query_tokens or not candidate_tokens:
            return 0

        query_set = set(query_tokens)
        candidate_set = set(candidate_tokens)
        overlap = len(query_set & candidate_set)
        ratio = overlap / max(1, len(query_set))
        return max(0, min(100, int(round(ratio * 100))))

    @classmethod
    def _estimate_compatibility_score(cls, query: str, title: str, artist: str) -> tuple[int, dict[str, int]]:
        query_tokens = cls._normalize_for_score(query)
        title_tokens = cls._normalize_for_score(title)
        artist_tokens = cls._normalize_for_score(artist)

        title_score = cls._token_overlap_score(query_tokens, title_tokens)
        artist_score = cls._token_overlap_score(query_tokens, artist_tokens)

        score = int(round((title_score * 0.7) + (artist_score * 0.3)))
        score = max(0, min(100, score))

        return score, {
            "title": title_score,
            "artist": artist_score,
        }

    @staticmethod
    def _resolve_target_stems(requested: Optional[list[str]]) -> list[str]:
        if requested is None:
            return list(settings.separation_target_stems)

        normalized = [stem_name.strip().lower() for stem_name in requested if stem_name and stem_name.strip()]
        if not normalized:
            return list(settings.separation_target_stems)

        seen: set[str] = set()
        filtered: list[str] = []
        for stem_name in normalized:
            if stem_name in SUPPORTED_STEMS and stem_name not in seen:
                filtered.append(stem_name)
                seen.add(stem_name)

        if not filtered:
            return list(settings.separation_target_stems)

        return filtered

    async def create_job(
        self,
        query: str,
        selected_track: Optional[SearchCandidate] = None,
        target_stems: Optional[list[str]] = None,
    ) -> JobStatus:
        now = datetime.utcnow()
        session_id = str(uuid4())
        resolved_target_stems = self._resolve_target_stems(target_stems)
        session_code = await asyncio.to_thread(
            self._store.create_session,
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
        async with self._lock:
            self._jobs[job.job_id] = job
            self._subscribers[job.job_id] = set()

        try:
            await self.add_session_event(
                job.session_id,
                stage=job.state.value,
                level="info",
                message=job.message,
                progress=job.progress,
            )
        except Exception as exc:
            logger.warning("Failed to persist initial event for %s: %s", job.session_id, exc)
        return job

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
        session = await self.get_job(session_id)
        if session is None:
            return None

        payload = await asyncio.to_thread(self._store.get_mix_state_payload, session_id)
        if payload is None:
            return self._default_mix_state()

        try:
            return MixState.model_validate(payload)
        except Exception:
            return self._default_mix_state()

    async def save_mix_state(self, session_id: str, update: MixStateUpdate) -> Optional[MixState]:
        current = await self.get_mix_state(session_id)
        if current is None:
            return None

        merged_per_stem = {**current.per_stem, **update.per_stem}
        next_master_gain = current.master_gain if update.master_gain is None else update.master_gain

        persisted_state = MixState(
            per_stem=merged_per_stem,
            master_gain=next_master_gain,
            updated_at=datetime.utcnow(),
        )

        payload = {
            "per_stem": {
                stem_name: stem_state.model_dump(mode="json")
                for stem_name, stem_state in persisted_state.per_stem.items()
            },
            "master_gain": persisted_state.master_gain,
        }

        await asyncio.to_thread(
            self._store.save_mix_state_payload,
            session_id,
            payload,
            persisted_state.updated_at,
        )

        return persisted_state

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
        session = await self.get_job(session_id)
        if session is None:
            return None

        now = datetime.utcnow()
        export_id = str(uuid4())
        export_job = await asyncio.to_thread(
            self._store.create_export_job,
            export_id=export_id,
            session_id=session_id,
            preset=preset,
            format_name=format_name,
            state=ExportState.queued,
            progress=0,
            created_at=now,
            updated_at=now,
        )

        async with self._lock:
            self._export_jobs[export_id] = export_job

        return export_job

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

    @staticmethod
    def _resolve_export_stems(session: JobStatus, options: dict[str, object]) -> list[str]:
        requested = options.get("stem_names")
        if isinstance(requested, list):
            normalized = [str(item).strip().lower() for item in requested if str(item).strip()]
            deduped: list[str] = []
            seen: set[str] = set()
            for stem_name in normalized:
                if stem_name in SUPPORTED_STEMS and stem_name not in seen:
                    deduped.append(stem_name)
                    seen.add(stem_name)
            if deduped:
                return deduped

        if session.target_stems:
            return list(session.target_stems)

        return list(settings.separation_target_stems)

    @staticmethod
    def _copy_export_stems(stems: dict[str, Path], target_dir: Path) -> list[Path]:
        copied: list[Path] = []
        target_dir.mkdir(parents=True, exist_ok=True)
        for stem_name, source_file in stems.items():
            target_file = target_dir / f"{stem_name}.wav"
            shutil.copy2(source_file, target_file)
            copied.append(target_file)
        return copied

    @staticmethod
    def _mix_stems_to_wav(stems: dict[str, Path], mix_state: MixState, output_path: Path) -> Path:
        stem_order = [name for name in SUPPORTED_STEMS if name in stems]
        if not stem_order:
            raise RuntimeError("No stems available to export mix")

        solo_stems = [name for name, state in mix_state.per_stem.items() if state.solo]
        active_stems: list[str] = []
        for stem_name in stem_order:
            stem_state = mix_state.per_stem.get(stem_name, StemMixState())
            if solo_stems and stem_name not in solo_stems:
                continue
            if stem_state.mute:
                continue
            active_stems.append(stem_name)

        if not active_stems:
            raise RuntimeError("No active stems available for mix export")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        command: list[str] = ["ffmpeg", "-y"]
        filters: list[str] = []
        amix_inputs: list[str] = []

        master_linear = math.pow(10.0, mix_state.master_gain / 20.0)
        for index, stem_name in enumerate(active_stems):
            command.extend(["-i", str(stems[stem_name])])
            stem_state = mix_state.per_stem.get(stem_name, StemMixState())
            stem_linear = math.pow(10.0, stem_state.gain / 20.0)
            volume_factor = max(0.0, stem_linear * master_linear)
            label = f"v{index}"
            filters.append(f"[{index}:a]volume={volume_factor:.6f}[{label}]")
            amix_inputs.append(f"[{label}]")

        filters.append(f"{''.join(amix_inputs)}amix=inputs={len(amix_inputs)}:normalize=0[m]")
        command.extend(["-filter_complex", ";".join(filters), "-map", "[m]", str(output_path)])

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("FFmpeg is required to export mix but was not found") from exc
        except subprocess.CalledProcessError as exc:
            stderr_output = (exc.stderr or "").strip()
            raise RuntimeError(f"FFmpeg failed while exporting mix: {stderr_output}") from exc

        return output_path

    @staticmethod
    def _zip_export_files(files: list[Path], zip_path: Path) -> Path:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                archive.write(file_path, arcname=file_path.name)
        return zip_path

    @staticmethod
    def _artifact_from_file(
        *,
        file_path: Path,
        kind: str,
        session_id: str,
        export_id: str,
    ) -> ExportArtifact:
        return ExportArtifact(
            kind=kind,
            file_name=file_path.name,
            path=file_path.as_posix(),
            size_bytes=file_path.stat().st_size if file_path.exists() else 0,
            download_url=JobService._build_export_download_url(session_id, export_id, file_path.name),
        )

    async def get_export_file_path(self, session_id: str, export_id: str, file_name: str) -> Optional[Path]:
        export_job = await self.get_export_job(session_id, export_id)
        if export_job is None:
            return None

        for artifact in export_job.output_files:
            if artifact.file_name != file_name:
                continue

            requested_file = Path(artifact.path).resolve()
            storage_root = settings.storage_root.resolve()

            try:
                requested_file.relative_to(storage_root)
            except ValueError:
                return None

            if requested_file.is_file():
                return requested_file

        return None

    async def run_export_pipeline(self, session_id: str, export_id: str, options: Optional[dict[str, object]] = None) -> None:
        runtime_options = options or {}

        try:
            export_job = await self.get_export_job(session_id, export_id)
            if export_job is None:
                return

            await self.update_export_job(
                session_id,
                export_id,
                state=ExportState.processing,
                progress=10,
            )

            session = await self.get_job(session_id)
            if session is None:
                raise RuntimeError("Session not found for export")
            if session.state != JobState.ready:
                raise RuntimeError("Session is not ready for export")
            if not session.stems:
                raise RuntimeError("Session has no stems to export")

            selected_stems = self._resolve_export_stems(session, runtime_options)
            stem_files: dict[str, Path] = {}
            for stem_name in selected_stems:
                stem_path = session.stems.get(stem_name)
                if not stem_path:
                    continue
                resolved = Path(stem_path).resolve()
                if resolved.is_file():
                    stem_files[stem_name] = resolved

            if not stem_files:
                raise RuntimeError("No stem files found for requested export")

            mix_state = await self.get_mix_state(session_id)
            if mix_state is None:
                mix_state = self._default_mix_state()

            export_dir = settings.exports_root / session_id / export_id
            export_dir.mkdir(parents=True, exist_ok=True)

            include_mix = export_job.preset in {"study_mix", "custom"}
            include_stems = export_job.preset in {"stems", "custom"}
            if export_job.preset == "custom":
                include_mix = bool(runtime_options.get("include_mix", True))
                include_stems = bool(runtime_options.get("include_stems", True))

            generated_files: list[tuple[Path, str]] = []

            if export_job.format == "wav":
                if include_mix:
                    mix_file = self._mix_stems_to_wav(stem_files, mix_state, export_dir / "mix_study.wav")
                    generated_files.append((mix_file, "mix"))

                if include_stems:
                    copied_stems = self._copy_export_stems(stem_files, export_dir / "stems")
                    generated_files.extend((file_path, "stem") for file_path in copied_stems)
            else:
                files_to_zip: list[Path] = []

                if include_mix:
                    mix_file = self._mix_stems_to_wav(stem_files, mix_state, export_dir / "mix_study.wav")
                    files_to_zip.append(mix_file)

                if include_stems or not include_mix:
                    files_to_zip.extend(stem_files.values())

                if not files_to_zip:
                    raise RuntimeError("No files selected for ZIP export")

                bundle = self._zip_export_files(files_to_zip, export_dir / "export_bundle.zip")
                generated_files.append((bundle, "zip"))

            if not generated_files:
                raise RuntimeError("Export generated no output files")

            artifacts = [
                self._artifact_from_file(
                    file_path=file_path,
                    kind=kind,
                    session_id=session_id,
                    export_id=export_id,
                )
                for file_path, kind in generated_files
            ]

            await self.update_export_job(
                session_id,
                export_id,
                state=ExportState.ready,
                progress=100,
                output_files=artifacts,
                error=None,
            )
        except Exception as exc:
            await self.update_export_job(
                session_id,
                export_id,
                state=ExportState.failed,
                progress=100,
                output_files=[],
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _clone_session_as_new_job(self, session_id: str) -> Optional[JobStatus]:
        source_job = await self.get_job(session_id)
        if source_job is None:
            return None

        if source_job.selected_track is None:
            raise ValueError("Selected source is unavailable for this session")

        return await self.create_job(
            source_job.query,
            selected_track=source_job.selected_track,
            target_stems=source_job.target_stems,
        )

    async def duplicate_session(self, session_id: str) -> Optional[JobStatus]:
        return await self._clone_session_as_new_job(session_id)

    async def reprocess_session(self, session_id: str) -> Optional[JobStatus]:
        return await self._clone_session_as_new_job(session_id)

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
                estimated_remaining_seconds = self._estimate_eta_seconds(
                    created_at=job.created_at,
                    progress=progress,
                    state=state,
                    now=now,
                )

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

    @staticmethod
    def _estimate_eta_seconds(
        *,
        created_at: datetime,
        progress: int,
        state: JobState,
        now: datetime,
    ) -> Optional[int]:
        if state in {JobState.ready, JobState.failed}:
            return 0
        if progress <= 0:
            return None

        elapsed_seconds = max(1.0, (now - created_at).total_seconds())
        remaining_progress = max(0, 100 - progress)
        estimate = round((elapsed_seconds * remaining_progress) / max(progress, 1))
        return max(0, min(int(estimate), 21600))

    async def run_pipeline(self, job_id: str) -> None:
        try:
            snapshot = await self.get_job(job_id)
            if snapshot is None or snapshot.selected_track is None:
                raise RuntimeError("No selected source available for this job")

            selected_title = snapshot.selected_track.title
            selected_url = snapshot.selected_track.url

            await self.update_job(
                job_id,
                state=JobState.downloading,
                progress=10,
                message=f"Downloading audio source: {selected_title}",
            )

            downloaded_audio_path = await asyncio.to_thread(
                self._download_audio_source,
                selected_url,
                job_id,
            )

            await self.update_job(
                job_id,
                state=JobState.downloading,
                progress=45,
                message=f"Audio downloaded: {downloaded_audio_path}",
            )

            await self.update_job(
                job_id,
                state=JobState.separating,
                progress=60,
                message="Running stem separation with Demucs",
            )

            stems, used_device = await asyncio.to_thread(
                self._run_demucs,
                downloaded_audio_path,
                job_id,
                snapshot.target_stems,
            )

            await self.update_job(
                job_id,
                state=JobState.separating,
                progress=92,
                message=f"Demucs separation completed on {used_device.upper()}",
                separation_device=used_device,
            )

            master_metrics = await asyncio.to_thread(self._analyze_master_metrics, stems, job_id)

            await self.update_job(
                job_id,
                state=JobState.ready,
                progress=100,
                message="Stems ready",
                stems=stems,
                separation_device=used_device,
                master_metrics=master_metrics,
            )
        except Exception as exc:  # pragma: no cover
            error_message = f"{type(exc).__name__}: {exc}"
            await self.update_job(
                job_id,
                state=JobState.failed,
                progress=100,
                message="Processing failed",
                error=error_message,
            )

    def _run_demucs(self, input_audio_path: str, job_id: str, target_stems: list[str]) -> tuple[Dict[str, str], str]:
        try:
            from demucs.separate import main as demucs_main
        except ImportError as exc:
            raise RuntimeError(
                "Demucs is not installed. Install backend/requirements.pipeline.txt before running separation"
            ) from exc

        settings.torch_home.mkdir(parents=True, exist_ok=True)
        os.environ["TORCH_HOME"] = str(settings.torch_home)

        final_output_dir = settings.stems_root / job_id
        temp_output_root = final_output_dir / "_demucs_output"

        final_output_dir.mkdir(parents=True, exist_ok=True)

        device_candidates = self._resolve_demucs_devices()
        last_error: Optional[Exception] = None

        for device in device_candidates:
            try:
                if temp_output_root.exists():
                    shutil.rmtree(temp_output_root)
                temp_output_root.mkdir(parents=True, exist_ok=True)

                demucs_segment = max(1, int(settings.separation_segment))

                demucs_args = [
                    "--name",
                    settings.separation_model,
                    "--device",
                    device,
                    "--segment",
                    str(demucs_segment),
                    "--overlap",
                    str(settings.separation_overlap),
                    "--shifts",
                    str(settings.separation_shifts),
                    "--out",
                    str(temp_output_root),
                    input_audio_path,
                ]

                demucs_main(demucs_args)
                stems = self._normalize_demucs_output(
                    temp_output_root,
                    final_output_dir,
                    target_stems,
                )
                if temp_output_root.exists():
                    shutil.rmtree(temp_output_root)
                return stems, device
            except SystemExit as exc:
                last_error = RuntimeError(f"Demucs exited with code {exc.code} on device '{device}'")
            except Exception as exc:  # pragma: no cover
                last_error = RuntimeError(f"Demucs failed on device '{device}': {exc}")

        raise RuntimeError(f"Unable to separate stems with Demucs. Last error: {last_error}")

    @staticmethod
    def _resolve_demucs_devices() -> list[str]:
        if settings.separation_device in {"cuda", "cpu"}:
            return [settings.separation_device]

        try:
            import torch

            if torch.cuda.is_available():
                return ["cuda", "cpu"]
        except Exception:
            pass

        return ["cpu"]

    @staticmethod
    def _normalize_demucs_output(
        temp_output_root: Path,
        final_output_dir: Path,
        stem_names: list[str],
    ) -> Dict[str, str]:
        stems: Dict[str, str] = {}

        for stem_name in stem_names:
            source_file = JobService._find_demucs_stem_file(temp_output_root, stem_name)
            if source_file is None:
                raise RuntimeError(f"Demucs output does not contain expected stem '{stem_name}.wav'")

            target_file = final_output_dir / f"{stem_name}.wav"
            shutil.copy2(source_file, target_file)
            stems[stem_name] = target_file.as_posix()

        return stems

    @staticmethod
    def _find_demucs_stem_file(temp_output_root: Path, stem_name: str) -> Optional[Path]:
        candidates = [
            candidate
            for candidate in temp_output_root.rglob(f"{stem_name}.wav")
            if candidate.is_file()
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda file: file.stat().st_mtime, reverse=True)
        return candidates[0]

    def _download_audio_source(self, source_url: str, job_id: str) -> str:
        target_dir = settings.storage_root / "raw" / job_id
        target_dir.mkdir(parents=True, exist_ok=True)

        output_template = str(target_dir / "source.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "restrictfilenames": True,
            "overwrites": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(source_url, download=True)
        except DownloadError as exc:
            raise RuntimeError(f"Failed to download audio with yt-dlp: {exc}") from exc

        downloaded_file = self._find_downloaded_audio_file(target_dir)
        if downloaded_file is None:
            raise RuntimeError("yt-dlp finished but no audio file was found in storage/raw")

        return downloaded_file.as_posix()

    @staticmethod
    def _find_downloaded_audio_file(target_dir: Path) -> Optional[Path]:
        if not target_dir.exists():
            return None

        preferred_extensions = [
            ".wav",
            ".m4a",
            ".mp3",
            ".webm",
            ".opus",
            ".ogg",
            ".aac",
        ]

        for extension in preferred_extensions:
            candidate = target_dir / f"source{extension}"
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                return candidate

        files = [
            file
            for file in target_dir.iterdir()
            if file.is_file() and file.stat().st_size > 0
        ]
        if not files:
            return None

        files.sort(key=lambda file: file.stat().st_mtime, reverse=True)
        return files[0]

    def _analyze_master_metrics(self, stems: dict[str, str], job_id: str) -> Optional[MasterMetrics]:
        stem_paths: dict[str, Path] = {}
        for stem_name, stem_path in stems.items():
            if stem_name not in SUPPORTED_STEMS:
                continue
            resolved = Path(stem_path).resolve()
            if resolved.is_file():
                stem_paths[stem_name] = resolved

        if not stem_paths:
            return None

        analysis_mix_path = (settings.stems_root / job_id / "_analysis_master.wav").resolve()
        try:
            try:
                self._mix_stems_to_wav(stem_paths, self._default_mix_state(), analysis_mix_path)
            except Exception as exc:
                logger.info("Master metrics skipped for %s: %s", job_id, exc)
                return None

            return self._probe_master_metrics(analysis_mix_path)
        finally:
            try:
                if analysis_mix_path.exists():
                    analysis_mix_path.unlink()
            except Exception:
                pass

    @staticmethod
    def _probe_master_metrics(audio_file: Path) -> Optional[MasterMetrics]:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio_file),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            return None
        except subprocess.CalledProcessError:
            return None

        output = f"{result.stdout or ''}\n{result.stderr or ''}"
        metric_match = re.findall(r"\{\s*\"input_i\"[\s\S]*?\}", output)
        if not metric_match:
            return None

        try:
            payload = json.loads(metric_match[-1])
            lufs = float(payload["input_i"])
            true_peak = float(payload["input_tp"])
        except Exception:
            return None

        headroom = max(0.0, -true_peak)
        return MasterMetrics(
            lufs=round(lufs, 2),
            true_peak_dbtp=round(true_peak, 2),
            headroom_db=round(headroom, 2),
        )


job_service = JobService()

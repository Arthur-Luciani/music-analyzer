from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import and_, desc, text
from sqlalchemy.orm import Session

from app.db.config import SessionLocal
from app.db.models import ExportJobORM, SessionEventORM, SessionMixStateORM, SessionORM
from app.models import (
    ExportArtifact,
    ExportJob,
    ExportState,
    JobState,
    JobStatus,
    MasterMetrics,
    SearchCandidate,
    SessionEvent,
)
from app.settings import settings


class SessionRepository:
    """ORM-backed repository for sessions."""

    def __init__(self, db_session: Optional[Session] = None) -> None:
        self._session = db_session
        self._session_factory = SessionLocal

    def _get_session(self) -> Session:
        return self._session or self._session_factory()

    @staticmethod
    def _serialize_candidate(candidate: Optional[SearchCandidate]) -> Optional[str]:
        if candidate is None:
            return None
        return json.dumps(candidate.model_dump(mode="json"), ensure_ascii=True)

    @staticmethod
    def _deserialize_candidate(raw: Optional[str]) -> Optional[SearchCandidate]:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return SearchCandidate.model_validate(payload)
        except Exception:
            return None

    @staticmethod
    def _to_json_payload(value: object) -> str:
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def _safe_state(raw: str) -> JobState:
        try:
            return JobState(raw)
        except Exception:
            return JobState.failed

    @staticmethod
    def _safe_export_state(raw: str) -> ExportState:
        try:
            return ExportState(raw)
        except Exception:
            return ExportState.failed

    def _ensure_session_counter(self, session: Session) -> None:
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS session_counter (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    last_value INTEGER NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO session_counter(id, last_value)
                VALUES (1, 0)
                ON CONFLICT(id) DO NOTHING
                """
            )
        )

    def _next_session_code(self, session: Session) -> str:
        try:
            self._ensure_session_counter(session)
            session.execute(
                text(
                    """
                    UPDATE session_counter
                    SET last_value = last_value + 1
                    WHERE id = 1
                    """
                )
            )
            result = session.execute(text("SELECT last_value FROM session_counter WHERE id = 1")).scalar()
            sequence = int(result or 0)
        except Exception:
            result = session.execute(
                text("SELECT MAX(CAST(SUBSTR(session_code, 4) AS INTEGER)) FROM sessions")
            ).scalar()
            sequence = int(result or 0) + 1
        return f"MX-{sequence:03d}"

    def create_session(
        self,
        *,
        session_id: str,
        query: str,
        selected_track: Optional[SearchCandidate],
        target_stems: list[str],
        state: JobState,
        progress: int,
        message: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> str:
        session = self._get_session()
        close_after = self._session is None
        try:
            session_code = self._next_session_code(session)
            orm_session = SessionORM(
                id=session_id,
                session_code=session_code,
                query=query,
                selected_track_json=self._serialize_candidate(selected_track),
                track_title=selected_track.title if selected_track else None,
                artist=selected_track.artist if selected_track else None,
                target_stems_json=self._to_json_payload(target_stems),
                state=state.value,
                progress=progress,
                message=message,
                stems_json=None,
                error=None,
                created_at=created_at,
                updated_at=updated_at,
            )
            session.add(orm_session)
            session.commit()
            return session_code
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def save_session(self, job: JobStatus) -> None:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_session = session.query(SessionORM).filter(SessionORM.id == job.session_id).first()
            if not orm_session:
                raise ValueError(f"Session {job.session_id} not found")

            orm_session.query = job.query
            orm_session.selected_track_json = self._serialize_candidate(job.selected_track)
            orm_session.track_title = job.selected_track.title if job.selected_track else None
            orm_session.artist = job.selected_track.artist if job.selected_track else None
            orm_session.target_stems_json = self._to_json_payload(job.target_stems)
            orm_session.state = job.state.value
            orm_session.progress = job.progress
            orm_session.message = job.message
            orm_session.stems_json = self._to_json_payload(job.stems) if job.stems is not None else None
            orm_session.error = job.error
            orm_session.eta_seconds = job.estimated_remaining_seconds
            orm_session.separation_device = job.separation_device
            orm_session.master_metrics_json = (
                self._to_json_payload(job.master_metrics.model_dump(mode="json"))
                if job.master_metrics is not None
                else None
            )
            orm_session.updated_at = job.updated_at

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def get_session(self, session_id: str) -> Optional[JobStatus]:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_session = session.query(SessionORM).filter(SessionORM.id == session_id).first()
            if not orm_session:
                return None
            return self._orm_to_job_status(orm_session)
        finally:
            if close_after:
                session.close()

    def list_sessions(
        self,
        *,
        query: Optional[str],
        status: Optional[JobState],
        created_from: Optional[datetime],
        created_to: Optional[datetime],
        page: int,
        page_size: int,
    ) -> tuple[list[JobStatus], int]:
        session = self._get_session()
        close_after = self._session is None
        try:
            q = session.query(SessionORM)

            if query:
                query_like = f"%{query.strip()}%"
                q = q.filter(
                    SessionORM.query.ilike(query_like)
                    | SessionORM.track_title.ilike(query_like)
                    | SessionORM.artist.ilike(query_like)
                    | SessionORM.session_code.ilike(query_like)
                )

            if status is not None:
                q = q.filter(SessionORM.state == status.value)

            if created_from is not None:
                q = q.filter(SessionORM.created_at >= created_from)

            if created_to is not None:
                q = q.filter(SessionORM.created_at <= created_to)

            total = q.count()

            offset = max(0, (page - 1) * page_size)
            limit = max(1, page_size)

            rows = q.order_by(desc(SessionORM.created_at)).offset(offset).limit(limit).all()
            jobs = [self._orm_to_job_status(row) for row in rows]
            return jobs, total
        finally:
            if close_after:
                session.close()

    def clear_session_data(self, session_id: str) -> None:
        """Removes events, exports, and stems directory for a session without deleting the session itself."""
        import shutil

        session = self._get_session()
        close_after = self._session is None
        try:
            # Delete related rows (exports and events)
            session.query(ExportJobORM).filter(ExportJobORM.session_id == session_id).delete(synchronize_session=False)
            session.query(SessionEventORM).filter(SessionEventORM.session_id == session_id).delete(synchronize_session=False)
            # We keep SessionMixStateORM because the user might want to keep their fader settings
            session.commit()

            # Remove stem audio files and any analysis from disk
            stems_dir = settings.stems_root / session_id
            try:
                if stems_dir.is_dir():
                    shutil.rmtree(stems_dir)
            except Exception:
                pass
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all associated data.
        
        Returns True if the session existed and was deleted, False otherwise.
        """
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_session = session.query(SessionORM).filter(SessionORM.id == session_id).first()
            if not orm_session:
                return False

            # Clear associated data first (stems, events, exports)
            self.clear_session_data(session_id)
            
            # Also delete mix state for a full delete
            session.query(SessionMixStateORM).filter(SessionMixStateORM.session_id == session_id).delete(synchronize_session=False)

            # Delete the session record
            session.delete(orm_session)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def cleanup_stale_sessions(self, older_than: datetime) -> int:
        """Deletes sessions that have not been updated since `older_than`."""
        session = self._get_session()
        close_after = self._session is None
        try:
            rows = session.query(SessionORM.id).filter(SessionORM.updated_at < older_than).all()
            deleted_count = 0
            for row in rows:
                if self.delete_session(row.id):
                    deleted_count += 1
            return deleted_count
        finally:
            if close_after:
                session.close()

    def get_mix_state_payload(self, session_id: str) -> Optional[dict[str, object]]:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_mix = session.query(SessionMixStateORM).filter(SessionMixStateORM.session_id == session_id).first()
            if not orm_mix:
                return None

            try:
                payload = json.loads(orm_mix.payload_json)
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}

            payload["updated_at"] = orm_mix.updated_at.isoformat()
            return payload
        finally:
            if close_after:
                session.close()

    def save_mix_state_payload(self, session_id: str, payload: dict[str, object], updated_at: datetime) -> None:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_mix = session.query(SessionMixStateORM).filter(SessionMixStateORM.session_id == session_id).first()
            payload_json = self._to_json_payload(payload)

            if orm_mix:
                orm_mix.payload_json = payload_json
                orm_mix.updated_at = updated_at
            else:
                orm_mix = SessionMixStateORM(
                    session_id=session_id,
                    payload_json=payload_json,
                    updated_at=updated_at,
                )
                session.add(orm_mix)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def create_export_job(
        self,
        *,
        export_id: str,
        session_id: str,
        preset: str,
        format_name: str,
        state: ExportState,
        progress: int,
        created_at: datetime,
        updated_at: datetime,
    ) -> ExportJob:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_export = ExportJobORM(
                id=export_id,
                session_id=session_id,
                preset=preset,
                format=format_name,
                state=state.value,
                progress=progress,
                output_json="[]",
                error=None,
                created_at=created_at,
                updated_at=updated_at,
            )
            session.add(orm_export)
            session.commit()

            return ExportJob(
                export_id=export_id,
                session_id=session_id,
                preset=preset,
                format=format_name,
                state=state,
                progress=progress,
                output_files=[],
                error=None,
                created_at=created_at,
                updated_at=updated_at,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def save_export_job(self, export_job: ExportJob) -> None:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_export = session.query(ExportJobORM).filter(ExportJobORM.id == export_job.export_id).first()
            if not orm_export:
                raise ValueError(f"Export {export_job.export_id} not found")

            orm_export.preset = export_job.preset
            orm_export.format = export_job.format
            orm_export.state = export_job.state.value
            orm_export.progress = export_job.progress
            orm_export.output_json = self._to_json_payload(
                [file_item.model_dump(mode="json") for file_item in export_job.output_files]
            )
            orm_export.error = export_job.error
            orm_export.updated_at = export_job.updated_at

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def get_export_job(self, session_id: str, export_id: str) -> Optional[ExportJob]:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_export = (
                session.query(ExportJobORM)
                .filter(
                    and_(
                        ExportJobORM.session_id == session_id,
                        ExportJobORM.id == export_id,
                    )
                )
                .first()
            )

            if not orm_export:
                return None

            return self._orm_to_export_job(orm_export)
        finally:
            if close_after:
                session.close()

    def list_export_jobs(self, session_id: str) -> list[ExportJob]:
        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(ExportJobORM)
                .filter(ExportJobORM.session_id == session_id)
                .order_by(desc(ExportJobORM.created_at))
                .all()
            )
            return [self._orm_to_export_job(row) for row in rows]
        finally:
            if close_after:
                session.close()

    def append_session_event(
        self,
        *,
        session_id: str,
        timestamp: datetime,
        stage: str,
        level: str,
        progress: int,
        message: str,
    ) -> None:
        session = self._get_session()
        close_after = self._session is None
        try:
            orm_event = SessionEventORM(
                session_id=session_id,
                ts=timestamp,
                stage=stage,
                level=level,
                progress=progress,
                message=message,
            )
            session.add(orm_event)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if close_after:
                session.close()

    def list_session_events(self, session_id: str) -> list[SessionEvent]:
        session = self._get_session()
        close_after = self._session is None
        try:
            rows = (
                session.query(SessionEventORM)
                .filter(SessionEventORM.session_id == session_id)
                .order_by(SessionEventORM.ts.asc())
                .all()
            )

            events: list[SessionEvent] = []
            for row in rows:
                progress = int(row.progress) if row.progress is not None else 0
                events.append(
                    SessionEvent(
                        timestamp=row.ts,
                        stage=row.stage,
                        level=row.level,
                        progress=max(0, min(100, progress)),
                        message=row.message,
                    )
                )

            return events
        finally:
            if close_after:
                session.close()

    def _orm_to_job_status(self, orm_session: SessionORM) -> JobStatus:
        target_stems = list(settings.separation_target_stems)
        if orm_session.target_stems_json:
            try:
                payload = json.loads(orm_session.target_stems_json)
                if isinstance(payload, list):
                    parsed = [str(item).strip().lower() for item in payload if str(item).strip()]
                    if parsed:
                        target_stems = parsed
            except Exception:
                pass

        stems_payload: Optional[Dict[str, str]] = None
        if orm_session.stems_json:
            try:
                parsed_stems = json.loads(orm_session.stems_json)
                if isinstance(parsed_stems, dict):
                    stems_payload = {str(key): str(value) for key, value in parsed_stems.items()}
            except Exception:
                stems_payload = None

        eta_seconds = None
        if orm_session.eta_seconds is not None:
            try:
                eta_seconds = max(0, int(orm_session.eta_seconds))
            except Exception:
                eta_seconds = None

        separation_device = None
        if isinstance(orm_session.separation_device, str):
            separation_device = orm_session.separation_device.strip().lower() or None

        master_metrics: Optional[MasterMetrics] = None
        if orm_session.master_metrics_json:
            try:
                payload = json.loads(orm_session.master_metrics_json)
                master_metrics = MasterMetrics.model_validate(payload)
            except Exception:
                master_metrics = None

        progress = int(orm_session.progress) if orm_session.progress is not None else 0

        return JobStatus(
            job_id=orm_session.id,
            session_id=orm_session.id,
            session_code=orm_session.session_code,
            query=orm_session.query,
            selected_track=self._deserialize_candidate(orm_session.selected_track_json),
            target_stems=target_stems,
            state=self._safe_state(orm_session.state),
            progress=max(0, min(100, progress)),
            message=orm_session.message,
            created_at=orm_session.created_at,
            updated_at=orm_session.updated_at,
            stems=stems_payload,
            error=orm_session.error,
            estimated_remaining_seconds=eta_seconds,
            separation_device=separation_device,
            master_metrics=master_metrics,
        )

    def _orm_to_export_job(self, orm_export: ExportJobORM) -> ExportJob:
        output_files: list[ExportArtifact] = []
        if orm_export.output_json:
            try:
                payload = json.loads(orm_export.output_json)
                if isinstance(payload, list):
                    output_files = [ExportArtifact.model_validate(item) for item in payload]
            except Exception:
                output_files = []

        progress = int(orm_export.progress) if orm_export.progress is not None else 0

        return ExportJob(
            export_id=orm_export.id,
            session_id=orm_export.session_id,
            preset=orm_export.preset,
            format=orm_export.format,
            state=self._safe_export_state(orm_export.state),
            progress=max(0, min(100, progress)),
            output_files=output_files,
            error=orm_export.error,
            created_at=orm_export.created_at,
            updated_at=orm_export.updated_at,
        )

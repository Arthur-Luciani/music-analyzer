import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.models import ExportArtifact, ExportJob, ExportState, JobState, JobStatus, MasterMetrics, SearchCandidate, SessionEvent
from app.settings import settings


class SQLiteSessionStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        session_code TEXT NOT NULL UNIQUE,
                        query TEXT NOT NULL,
                        selected_track_json TEXT,
                        track_title TEXT,
                        artist TEXT,
                        target_stems_json TEXT NOT NULL,
                        state TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        message TEXT NOT NULL,
                        stems_json TEXT,
                        error TEXT,
                        eta_seconds INTEGER,
                        separation_device TEXT,
                        master_metrics_json TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                existing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()}
                if "eta_seconds" not in existing_columns:
                    connection.execute("ALTER TABLE sessions ADD COLUMN eta_seconds INTEGER")
                if "separation_device" not in existing_columns:
                    connection.execute("ALTER TABLE sessions ADD COLUMN separation_device TEXT")
                if "master_metrics_json" not in existing_columns:
                    connection.execute("ALTER TABLE sessions ADD COLUMN master_metrics_json TEXT")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_counter (
                        id INTEGER PRIMARY KEY CHECK(id = 1),
                        last_value INTEGER NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO session_counter(id, last_value)
                    VALUES (1, 0)
                    ON CONFLICT(id) DO NOTHING
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sessions_created_at
                    ON sessions(created_at DESC)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sessions_state
                    ON sessions(state)
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_mix_state (
                        session_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS export_jobs (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        preset TEXT NOT NULL,
                        format TEXT NOT NULL,
                        state TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        output_json TEXT,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_export_jobs_session_created
                    ON export_jobs(session_id, created_at DESC)
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        level TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        message TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_session_events_ts
                    ON session_events(session_id, ts ASC)
                    """
                )

    @staticmethod
    def _to_json_payload(value: object) -> str:
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def _serialize_candidate(candidate: Optional[SearchCandidate]) -> Optional[str]:
        if candidate is None:
            return None
        return SQLiteSessionStore._to_json_payload(candidate.model_dump(mode="json"))

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
    def _parse_datetime(raw: str) -> datetime:
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return datetime.utcnow()

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

    def _next_session_code(self, connection: sqlite3.Connection) -> str:
        connection.execute(
            """
            UPDATE session_counter
            SET last_value = last_value + 1
            WHERE id = 1
            """
        )
        row = connection.execute("SELECT last_value FROM session_counter WHERE id = 1").fetchone()
        sequence = int(row["last_value"]) if row is not None else 0
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
        with self._lock:
            with self._connect() as connection:
                session_code = self._next_session_code(connection)
                connection.execute(
                    """
                    INSERT INTO sessions (
                        id, session_code, query, selected_track_json,
                        track_title, artist, target_stems_json,
                        state, progress, message, stems_json, error,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        session_code,
                        query,
                        self._serialize_candidate(selected_track),
                        selected_track.title if selected_track else None,
                        selected_track.artist if selected_track else None,
                        self._to_json_payload(target_stems),
                        state.value,
                        progress,
                        message,
                        None,
                        None,
                        created_at.isoformat(),
                        updated_at.isoformat(),
                    ),
                )
                return session_code

    def save_session(self, job: JobStatus) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE sessions
                    SET
                        query = ?,
                        selected_track_json = ?,
                        track_title = ?,
                        artist = ?,
                        target_stems_json = ?,
                        state = ?,
                        progress = ?,
                        message = ?,
                        stems_json = ?,
                        error = ?,
                        eta_seconds = ?,
                        separation_device = ?,
                        master_metrics_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        job.query,
                        self._serialize_candidate(job.selected_track),
                        job.selected_track.title if job.selected_track else None,
                        job.selected_track.artist if job.selected_track else None,
                        self._to_json_payload(job.target_stems),
                        job.state.value,
                        job.progress,
                        job.message,
                        self._to_json_payload(job.stems) if job.stems is not None else None,
                        job.error,
                        job.estimated_remaining_seconds,
                        job.separation_device,
                        self._to_json_payload(job.master_metrics.model_dump(mode="json")) if job.master_metrics is not None else None,
                        job.updated_at.isoformat(),
                        job.session_id,
                    ),
                )

    def get_session(self, session_id: str) -> Optional[JobStatus]:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job_status(row)

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
        where_clauses: list[str] = []
        params: list[object] = []

        if query:
            query_like = f"%{query.strip()}%"
            where_clauses.append("(query LIKE ? OR track_title LIKE ? OR artist LIKE ? OR session_code LIKE ?)")
            params.extend([query_like, query_like, query_like, query_like])

        if status is not None:
            where_clauses.append("state = ?")
            params.append(status.value)

        if created_from is not None:
            where_clauses.append("created_at >= ?")
            params.append(created_from.isoformat())

        if created_to is not None:
            where_clauses.append("created_at <= ?")
            params.append(created_to.isoformat())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        limit = max(1, page_size)
        offset = max(0, (page - 1) * page_size)

        with self._lock:
            with self._connect() as connection:
                total_row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM sessions {where_sql}",
                    params,
                ).fetchone()
                total = int(total_row["total"]) if total_row is not None else 0

                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM sessions
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [*params, limit, offset],
                ).fetchall()

        jobs = [self._row_to_job_status(row) for row in rows]
        return jobs, total

    def get_mix_state_payload(self, session_id: str) -> Optional[dict[str, object]]:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT payload_json, updated_at
                    FROM session_mix_state
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

        if row is None:
            return None

        try:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        payload["updated_at"] = row["updated_at"]
        return payload

    def save_mix_state_payload(self, session_id: str, payload: dict[str, object], updated_at: datetime) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO session_mix_state (session_id, payload_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id)
                    DO UPDATE SET
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (session_id, self._to_json_payload(payload), updated_at.isoformat()),
                )

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
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO export_jobs (
                        id, session_id, preset, format, state,
                        progress, output_json, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        export_id,
                        session_id,
                        preset,
                        format_name,
                        state.value,
                        progress,
                        self._to_json_payload([]),
                        None,
                        created_at.isoformat(),
                        updated_at.isoformat(),
                    ),
                )

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

    def save_export_job(self, export_job: ExportJob) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE export_jobs
                    SET
                        preset = ?,
                        format = ?,
                        state = ?,
                        progress = ?,
                        output_json = ?,
                        error = ?,
                        updated_at = ?
                    WHERE id = ? AND session_id = ?
                    """,
                    (
                        export_job.preset,
                        export_job.format,
                        export_job.state.value,
                        export_job.progress,
                        self._to_json_payload([file_item.model_dump(mode="json") for file_item in export_job.output_files]),
                        export_job.error,
                        export_job.updated_at.isoformat(),
                        export_job.export_id,
                        export_job.session_id,
                    ),
                )

    def get_export_job(self, session_id: str, export_id: str) -> Optional[ExportJob]:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM export_jobs
                    WHERE session_id = ? AND id = ?
                    """,
                    (session_id, export_id),
                ).fetchone()

        if row is None:
            return None
        return self._row_to_export_job(row)

    def list_export_jobs(self, session_id: str) -> list[ExportJob]:
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM export_jobs
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    """,
                    (session_id,),
                ).fetchall()

        return [self._row_to_export_job(row) for row in rows]

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
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO session_events (session_id, ts, stage, level, progress, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, timestamp.isoformat(), stage, level, progress, message),
                )

    def list_session_events(self, session_id: str) -> list[SessionEvent]:
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT ts, stage, level, progress, message
                    FROM session_events
                    WHERE session_id = ?
                    ORDER BY ts ASC
                    """,
                    (session_id,),
                ).fetchall()

        events: list[SessionEvent] = []
        for row in rows:
            events.append(
                SessionEvent(
                    timestamp=self._parse_datetime(row["ts"]),
                    stage=row["stage"],
                    level=row["level"],
                    progress=max(0, min(100, int(row["progress"]))),
                    message=row["message"],
                )
            )

        return events

    def _row_to_job_status(self, row: sqlite3.Row) -> JobStatus:
        target_stems_raw = row["target_stems_json"]
        stems_raw = row["stems_json"]

        target_stems = list(settings.separation_target_stems)
        if target_stems_raw:
            try:
                payload = json.loads(target_stems_raw)
                if isinstance(payload, list):
                    parsed = [str(item).strip().lower() for item in payload if str(item).strip()]
                    if parsed:
                        target_stems = parsed
            except Exception:
                pass

        stems_payload: Optional[Dict[str, str]] = None
        if stems_raw:
            try:
                parsed_stems = json.loads(stems_raw)
                if isinstance(parsed_stems, dict):
                    stems_payload = {str(key): str(value) for key, value in parsed_stems.items()}
            except Exception:
                stems_payload = None

        raw_eta = row["eta_seconds"] if "eta_seconds" in row.keys() else None
        eta_seconds = None
        if raw_eta is not None:
            try:
                eta_seconds = max(0, int(raw_eta))
            except Exception:
                eta_seconds = None

        separation_device = row["separation_device"] if "separation_device" in row.keys() else None
        if isinstance(separation_device, str):
            separation_device = separation_device.strip().lower() or None
        else:
            separation_device = None

        master_metrics: Optional[MasterMetrics] = None
        raw_master_metrics = row["master_metrics_json"] if "master_metrics_json" in row.keys() else None
        if raw_master_metrics:
            try:
                payload = json.loads(raw_master_metrics)
                master_metrics = MasterMetrics.model_validate(payload)
            except Exception:
                master_metrics = None

        return JobStatus(
            job_id=row["id"],
            session_id=row["id"],
            session_code=row["session_code"],
            query=row["query"],
            selected_track=self._deserialize_candidate(row["selected_track_json"]),
            target_stems=target_stems,
            state=self._safe_state(row["state"]),
            progress=max(0, min(100, int(row["progress"]))),
            message=row["message"],
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
            stems=stems_payload,
            error=row["error"],
            estimated_remaining_seconds=eta_seconds,
            separation_device=separation_device,
            master_metrics=master_metrics,
        )

    def _row_to_export_job(self, row: sqlite3.Row) -> ExportJob:
        output_files: list[ExportArtifact] = []
        raw_output = row["output_json"]
        if raw_output:
            try:
                payload = json.loads(raw_output)
                if isinstance(payload, list):
                    output_files = [ExportArtifact.model_validate(item) for item in payload]
            except Exception:
                output_files = []

        return ExportJob(
            export_id=row["id"],
            session_id=row["session_id"],
            preset=row["preset"],
            format=row["format"],
            state=self._safe_export_state(row["state"]),
            progress=max(0, min(100, int(row["progress"]))),
            output_files=output_files,
            error=row["error"],
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )
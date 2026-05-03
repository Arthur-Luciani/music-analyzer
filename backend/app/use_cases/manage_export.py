import asyncio
import logging
import math
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.models import ExportArtifact, ExportJob, ExportState, JobState, JobStatus, MixState, StemMixState
from app.settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")


@dataclass
class CreateExportUseCase:
    _job_service: object

    async def execute(self, session_id: str, preset: str, format_name: str) -> Optional[ExportJob]:
        session = await self._job_service.get_job(session_id)
        if session is None:
            return None

        now = datetime.utcnow()
        export_id = str(uuid4())
        export_job = await asyncio.to_thread(
            self._job_service._store.create_export_job,
            export_id=export_id,
            session_id=session_id,
            preset=preset,
            format_name=format_name,
            state=ExportState.queued,
            progress=0,
            created_at=now,
            updated_at=now,
        )

        async with self._job_service._lock:
            self._job_service._export_jobs[export_id] = export_job

        return export_job


@dataclass
class RunExportUseCase:
    _job_service: object

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
            target_file = target_dir / f"{stem_name}{source_file.suffix}"
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

    def _artifact_from_file(
        self,
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
            download_url=self._job_service._build_export_download_url(session_id, export_id, file_path.name),
        )

    async def execute(self, session_id: str, export_id: str, options: Optional[dict[str, object]] = None) -> None:
        runtime_options = options or {}

        try:
            export_job = await self._job_service.get_export_job(session_id, export_id)
            if export_job is None:
                return

            await self._job_service.update_export_job(
                session_id,
                export_id,
                state=ExportState.processing,
                progress=10,
            )

            session = await self._job_service.get_job(session_id)
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

            mix_state = await self._job_service.get_mix_state(session_id)
            if mix_state is None:
                mix_state = self._job_service._default_mix_state()

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

            await self._job_service.update_export_job(
                session_id,
                export_id,
                state=ExportState.ready,
                progress=100,
                output_files=artifacts,
                error=None,
            )
        except Exception as exc:
            await self._job_service.update_export_job(
                session_id,
                export_id,
                state=ExportState.failed,
                progress=100,
                output_files=[],
                error=f"{type(exc).__name__}: {exc}",
            )

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.models import JobState, MasterMetrics
from app.settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")


@dataclass
class ProcessSessionUseCase:
    _job_service: object

    async def execute(self, job_id: str) -> None:
        try:
            snapshot = await self._job_service.get_job(job_id)
            if snapshot is None or snapshot.selected_track is None:
                raise RuntimeError("No selected source available for this job")

            selected_title = snapshot.selected_track.title
            selected_url = snapshot.selected_track.url

            await self._job_service.update_job(
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

            await self._job_service.update_job(
                job_id,
                state=JobState.downloading,
                progress=45,
                message=f"Audio downloaded: {downloaded_audio_path}",
            )

            await self._job_service.update_job(
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

            await self._job_service.update_job(
                job_id,
                state=JobState.separating,
                progress=92,
                message=f"Demucs separation completed on {used_device.upper()}",
                separation_device=used_device,
            )

            master_metrics = await asyncio.to_thread(self._analyze_master_metrics, stems, job_id)

            await self._job_service.update_job(
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
            await self._job_service.update_job(
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
            source_file = ProcessSessionUseCase._find_demucs_stem_file(temp_output_root, stem_name)
            if source_file is None:
                raise RuntimeError(f"Demucs output does not contain expected stem '{stem_name}.wav'")

            target_file = final_output_dir / f"{stem_name}.mp3"
            ProcessSessionUseCase._compress_to_mp3(source_file, target_file)
            stems[stem_name] = target_file.as_posix()

        return stems

    @staticmethod
    def _compress_to_mp3(source_file: Path, target_file: Path) -> None:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_file),
            "-b:a",
            "320k",
            str(target_file),
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to compress stem to MP3: {exc}")

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
        ydl_opts = self._build_ytdlp_options(output_template)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(source_url, download=True)
        except DownloadError as exc:
            raise RuntimeError(self._format_ytdlp_download_error(exc)) from exc

        downloaded_file = self._find_downloaded_audio_file(target_dir)
        if downloaded_file is None:
            raise RuntimeError("yt-dlp finished but no audio file was found in storage/raw")

        return downloaded_file.as_posix()

    @staticmethod
    def _build_ytdlp_options(output_template: str) -> dict[str, object]:
        ydl_opts: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "restrictfilenames": True,
            "overwrites": True,
        }

        cookie_file = settings.yt_dlp_cookie_file
        if cookie_file is not None:
            ydl_opts["cookiefile"] = str(cookie_file)

        return ydl_opts

    @staticmethod
    def _format_ytdlp_download_error(exc: DownloadError) -> str:
        message = str(exc)
        lower_message = message.lower()

        if "sign in to confirm" in lower_message or "cookies" in lower_message:
            cookie_hint = "Defina YTDLP_COOKIE_FILE com um arquivo de cookies exportado do navegador."
            return f"Failed to download audio with yt-dlp: {message}. {cookie_hint}"

        return f"Failed to download audio with yt-dlp: {message}"

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
        from app.use_cases.manage_export import RunExportUseCase
        
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
                RunExportUseCase._mix_stems_to_wav(stem_paths, self._job_service._default_mix_state(), analysis_mix_path)
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

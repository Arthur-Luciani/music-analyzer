from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from yt_dlp.utils import YoutubeDLError

from app.use_cases.process_session import ProcessSessionUseCase


def test_build_ytdlp_options_includes_cookie_file(monkeypatch):
    cookie_file = Path("c:/tmp/ytdlp-cookies.txt")
    monkeypatch.setattr(
        "app.use_cases.process_session.settings",
        SimpleNamespace(yt_dlp_cookie_file=cookie_file),
    )

    options = ProcessSessionUseCase._build_ytdlp_options("/tmp/source.%(ext)s")

    assert options["cookiefile"] == str(cookie_file)
    assert options["outtmpl"] == "/tmp/source.%(ext)s"


def test_format_ytdlp_download_error_adds_cookie_hint_for_auth_blocks():
    error = YoutubeDLError("ERROR: [youtube] abc123: Sign in to confirm you’re not a bot.")

    message = ProcessSessionUseCase._format_ytdlp_download_error(error)

    assert "YTDLP_COOKIE_FILE" in message
    assert "Sign in to confirm" in message


def test_download_audio_source_passes_cookie_file(monkeypatch, tmp_path):
    cookie_file = Path("c:/tmp/ytdlp-cookies.txt")
    monkeypatch.setattr(
        "app.use_cases.process_session.settings",
        SimpleNamespace(storage_root=tmp_path, yt_dlp_cookie_file=cookie_file),
    )

    fake_ydl = Mock()
    fake_ydl.__enter__ = Mock(return_value=fake_ydl)
    fake_ydl.__exit__ = Mock(return_value=None)
    fake_ydl.extract_info = Mock(return_value=None)

    with patch("app.use_cases.process_session.YoutubeDL", return_value=fake_ydl) as mock_ytdl:
        with patch.object(ProcessSessionUseCase, "_find_downloaded_audio_file", return_value=tmp_path / "source.m4a"):
            service = ProcessSessionUseCase(_job_service=Mock())
            result = service._download_audio_source("https://www.youtube.com/watch?v=abc123", "job-1")

    assert result.endswith("source.m4a")
    mock_ytdl.assert_called_once()
    assert mock_ytdl.call_args.args[0]["cookiefile"] == str(cookie_file)


def test_download_audio_source_catches_unavailable_video_error(monkeypatch, tmp_path):
    import pytest
    from yt_dlp.utils import UnavailableVideoError

    monkeypatch.setattr(
        "app.use_cases.process_session.settings",
        SimpleNamespace(storage_root=tmp_path, yt_dlp_cookie_file=None),
    )

    fake_ydl = Mock()
    fake_ydl.__enter__ = Mock(return_value=fake_ydl)
    fake_ydl.__exit__ = Mock(return_value=None)
    fake_ydl.extract_info = Mock(side_effect=UnavailableVideoError("Video unavailable"))

    with patch("app.use_cases.process_session.YoutubeDL", return_value=fake_ydl):
        service = ProcessSessionUseCase(_job_service=Mock())
        with pytest.raises(RuntimeError) as exc_info:
            service._download_audio_source("https://www.youtube.com/watch?v=abc123", "job-1")

    assert "Failed to download audio with yt-dlp: Unable to download video: Video unavailable" in str(exc_info.value)
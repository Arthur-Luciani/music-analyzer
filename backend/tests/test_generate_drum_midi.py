from __future__ import annotations

from datetime import datetime

import pytest

from app.models.drum_analysis import DrumAnalysis, DrumHit
from app.models.market_midi import MarketMidiMatchResult
from app.use_cases.generate_drum_midi import GenerateDrumMidiUseCase


@pytest.fixture()
def isolated_stems_root(tmp_path):
    from app.settings import settings as real_settings

    original_stems_root = real_settings.stems_root
    stems_root = tmp_path / "stems"
    stems_root.mkdir(parents=True, exist_ok=True)
    object.__setattr__(real_settings, "stems_root", stems_root)
    try:
        yield real_settings
    finally:
        object.__setattr__(real_settings, "stems_root", original_stems_root)


def _write_analysis(stems_root, session_id: str, *, is_corrected: bool) -> DrumAnalysis:
    session_dir = stems_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    analysis = DrumAnalysis(
        bpm=120.0,
        duration_seconds=5.0,
        beat_count=10,
        beats=[i * 0.5 for i in range(10)],
        hits=[DrumHit(time=i * 0.5, type="kick", velocity=0.8, confidence=1.0) for i in range(10)],
        analyzed_at=datetime.utcnow(),
        status="complete",
        is_corrected=is_corrected,
    )
    (session_dir / "drum_analysis.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return analysis


def _write_market_match(stems_root, session_id: str, *, applied: bool) -> None:
    session_dir = stems_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    result = MarketMidiMatchResult(
        status="applied" if applied else "no_match",
        applied=applied,
        matched_artist="Test Artist" if applied else None,
        matched_title="Test Song" if applied else None,
        checked_at=datetime.utcnow(),
    )
    (session_dir / "market_midi_match.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_regenerates_when_no_market_midi_applied(isolated_stems_root):
    session_id = "session-no-market"
    _write_analysis(isolated_stems_root.stems_root, session_id, is_corrected=False)

    output_path = isolated_stems_root.stems_root / session_id / "drum_transcription.mid"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"sentinel-content")

    use_case = GenerateDrumMidiUseCase(_job_service=None)
    result_path = await use_case.execute(session_id, format="midi")

    assert result_path == output_path
    assert output_path.read_bytes() != b"sentinel-content"


@pytest.mark.asyncio
async def test_keeps_market_midi_file_untouched_when_applied_and_not_corrected(isolated_stems_root):
    session_id = "session-market-applied"
    _write_analysis(isolated_stems_root.stems_root, session_id, is_corrected=False)
    _write_market_match(isolated_stems_root.stems_root, session_id, applied=True)

    output_path = isolated_stems_root.stems_root / session_id / "drum_transcription.mid"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"sentinel-content")

    use_case = GenerateDrumMidiUseCase(_job_service=None)
    result_path = await use_case.execute(session_id, format="midi")

    assert result_path == output_path
    assert output_path.read_bytes() == b"sentinel-content"


@pytest.mark.asyncio
async def test_manual_correction_takes_precedence_over_market_midi(isolated_stems_root):
    session_id = "session-corrected"
    _write_analysis(isolated_stems_root.stems_root, session_id, is_corrected=True)
    _write_market_match(isolated_stems_root.stems_root, session_id, applied=True)

    output_path = isolated_stems_root.stems_root / session_id / "drum_transcription.mid"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"sentinel-content")

    use_case = GenerateDrumMidiUseCase(_job_service=None)
    result_path = await use_case.execute(session_id, format="midi")

    assert result_path == output_path
    assert output_path.read_bytes() != b"sentinel-content"

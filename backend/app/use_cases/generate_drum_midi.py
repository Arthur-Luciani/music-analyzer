import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from app.models.drum_analysis import DrumAnalysis, DrumHit
from app.settings import settings

logger = logging.getLogger(__name__)

HIT_TO_MIDI_NOTE = {
    "kick":   36,
    "snare":  38,
    "hihat":  42,
    "tom":    47,
    "cymbal": 49,
}

MIDI_VELOCITY_SCALE = 127

@dataclass
class GenerateDrumMidiUseCase:
    _job_service: object

    async def execute(self, session_id: str, format: str = "midi") -> Optional[Path]:
        """Gera arquivo MIDI ou MusicXML a partir do DrumAnalysis salvo."""
        import asyncio
        analysis = await asyncio.to_thread(
            self._load_analysis, session_id
        )
        if analysis is None or not analysis.hits:
            logger.warning(f"No analysis or hits found for session {session_id}")
            return None

        # Garantir BPM válido
        bpm = analysis.bpm if analysis.bpm > 0 else 120.0

        if format == "midi":
            output_path = settings.stems_root / session_id / "drum_transcription.mid"
            await asyncio.to_thread(self._write_midi, analysis, bpm, output_path)
            return output_path
        elif format == "musicxml":
            midi_path = settings.stems_root / session_id / "drum_transcription.mid"
            if not midi_path.exists():
                await asyncio.to_thread(self._write_midi, analysis, bpm, midi_path)
            
            output_path = settings.stems_root / session_id / "drum_transcription.musicxml"
            await asyncio.to_thread(self._write_musicxml, analysis, midi_path, output_path)
            return output_path
            
        return None

    @staticmethod
    def _load_analysis(session_id: str) -> Optional[DrumAnalysis]:
        from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
        return AnalyzeDrumStemUseCase.load_saved_analysis(session_id)

    @staticmethod
    def _write_midi(analysis: DrumAnalysis, bpm: float, output_path: Path) -> None:
        import pretty_midi

        # Cria MIDI com BPM correto
        midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

        for hit in analysis.hits:
            if hit.type == "unknown":
                continue

            note_number = HIT_TO_MIDI_NOTE.get(hit.type, 38)
            velocity = max(1, min(127, int(hit.velocity * MIDI_VELOCITY_SCALE)))

            note = pretty_midi.Note(
                velocity=velocity,
                pitch=note_number,
                start=hit.time,
                end=hit.time + 0.05,
            )
            drums.notes.append(note)

        midi.instruments.append(drums)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        midi.write(str(output_path))
        logger.info(f"MIDI written to {output_path} ({len(drums.notes)} notes)")

    @staticmethod
    def _write_musicxml(analysis: DrumAnalysis, midi_path: Path, output_path: Path) -> None:
        from music21 import converter, stream, metadata
        
        # Carregar o MIDI
        score = converter.parse(str(midi_path))
        
        # Adicionar metadados
        score.insert(0, metadata.Metadata())
        score.metadata.title = "Drum Transcription"
        score.metadata.composer = "Music Analyzer AI"
        
        # Quantização é feita automaticamente pelo music21 ao importar MIDI
        # mas podemos forçar se necessário
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        score.write("musicxml", fp=str(output_path))
        logger.info(f"MusicXML written to {output_path}")

def quantize_hits(hits: list[DrumHit], bpm: float, grid: str = "16") -> list[DrumHit]:
    """Encaixa cada hit na subdivisão mais próxima."""
    beat_duration = 60.0 / bpm
    grid_duration = beat_duration / (int(grid) / 4)

    quantized = []
    for hit in hits:
        grid_position = round(hit.time / grid_duration)
        quantized_time = grid_position * grid_duration
        quantized.append(hit.model_copy(update={"time": quantized_time}))

    return quantized

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from app.models.drum_analysis import DrumAnalysis, DrumHit
from app.services.drum_pitch_map import HIT_TYPE_TO_GM_PITCH, get_staff_position
from app.settings import settings

logger = logging.getLogger(__name__)

MIDI_VELOCITY_SCALE = 127
NOTE_GRID = "16"  # subdivisão (semicolcheia) usada pra quantizar a partitura

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
            if not await asyncio.to_thread(self._should_keep_market_midi, session_id, analysis, output_path):
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
    def _should_keep_market_midi(session_id: str, analysis: DrumAnalysis, output_path: Path) -> bool:
        """Evita reescrever `drum_transcription.mid` com a versão ADTOF quando
        um MIDI de mercado já foi aplicado — a menos que o usuário tenha
        corrigido manualmente os hits, que sempre tem precedência."""
        if analysis.is_corrected or not output_path.exists():
            return False

        from app.use_cases.match_market_midi import MatchMarketMidiUseCase
        market_result = MatchMarketMidiUseCase.load_saved_result(session_id)
        return bool(market_result and market_result.status == "applied")

    @staticmethod
    def _write_midi(analysis: DrumAnalysis, bpm: float, output_path: Path) -> None:
        import pretty_midi

        # Cria MIDI com BPM correto
        midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

        for hit in analysis.hits:
            if hit.type == "unknown":
                continue

            note_number = HIT_TYPE_TO_GM_PITCH.get(hit.type, 38)
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
        """Constrói a partitura diretamente do MIDI ativo (`midi_path` — o
        gerado pelo ADTOF ou o de mercado alinhado, o que estiver em vigor),
        mapeando cada pitch GM pra uma posição de pauta de bateria própria
        (ver `drum_pitch_map.GM_PITCH_TO_STAFF_POSITION`). Não usamos mais
        `converter.parse` + import genérico de MIDI: o music21 cria as notas
        como `Unpitched` mas nunca ajusta displayStep/displayOctave por
        conta própria, então tudo caía na mesma linha da pauta (B4, o
        default da classe) — bumbo, caixa e chimbal indistinguíveis.
        """
        import pretty_midi
        from music21 import clef, duration as m21duration, meter, metadata, stream, tempo
        from music21.note import Rest, Unpitched
        from music21.percussion import PercussionChord

        bpm = analysis.bpm if analysis.bpm > 0 else 120.0
        beat_duration = 60.0 / bpm
        grid_duration = beat_duration / (int(NOTE_GRID) / 4)
        grid_quarter_length = 4.0 / int(NOTE_GRID)

        pm = pretty_midi.PrettyMIDI(str(midi_path))
        raw_notes: list[tuple[float, int]] = [
            (note.start, note.pitch)
            for instrument in pm.instruments
            if instrument.is_drum
            for note in instrument.notes
        ]
        raw_notes.sort(key=lambda item: item[0])

        last_note_end = max((t for t, _ in raw_notes), default=0.0) + grid_duration
        total_duration = max(last_note_end, analysis.duration_seconds)
        num_slots = max(1, round(total_duration / grid_duration))

        slots: dict[int, set[int]] = {}
        for time, pitch in raw_notes:
            slot = max(0, min(num_slots - 1, round(time / grid_duration)))
            slots.setdefault(slot, set()).add(pitch)

        part = stream.Part()
        part.partName = "Bateria"
        part.append(clef.PercussionClef())
        part.append(meter.TimeSignature(analysis.time_signature or "4/4"))
        part.append(tempo.MetronomeMark(number=round(bpm, 1)))

        for slot_index in range(num_slots):
            pitches = slots.get(slot_index)
            if not pitches:
                rest = Rest()
                rest.duration = m21duration.Duration(grid_quarter_length)
                part.append(rest)
                continue

            unpitched_notes = []
            for pitch in sorted(pitches):
                step, octave, notehead = get_staff_position(pitch)
                unpitched = Unpitched()
                unpitched.displayStep = step
                unpitched.displayOctave = octave
                unpitched.notehead = notehead
                unpitched.duration = m21duration.Duration(grid_quarter_length)
                unpitched_notes.append(unpitched)

            if len(unpitched_notes) == 1:
                part.append(unpitched_notes[0])
            else:
                chord = PercussionChord(unpitched_notes)
                chord.duration = m21duration.Duration(grid_quarter_length)
                part.append(chord)

        part.makeMeasures(inPlace=True)

        score = stream.Score()
        score.insert(0, part)
        score.insert(0, metadata.Metadata())
        score.metadata.title = "Drum Transcription"
        score.metadata.composer = "Music Analyzer AI"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        score.write("musicxml", fp=str(output_path))
        logger.info(
            f"MusicXML written to {output_path} "
            f"({len(slots)} note slots of {num_slots}, grid=1/{NOTE_GRID})"
        )

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

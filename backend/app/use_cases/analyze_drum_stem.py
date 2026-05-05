from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np
import librosa

from app.models.drum_analysis import DrumAnalysis, DrumHit
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AnalyzeDrumStemUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[DrumAnalysis]:
        job = await self._job_service.get_job(session_id)
        if job is None or not job.stems or "drums" not in job.stems:
            logger.warning(f"Job not found or drums stem missing for session {session_id}")
            return None

        raw_path = job.stems["drums"]
        if raw_path.startswith("/app/storage/"):
            # Converter caminho do Docker para local
            # /app/storage/stems/abc/drums.mp3 -> stems/abc/drums.mp3
            relative_part = raw_path.replace("/app/storage/", "", 1)
            drum_stem_path = settings.storage_root / relative_part
        else:
            drum_stem_path = Path(raw_path)

        if not drum_stem_path.is_file():
            logger.warning(f"Drum stem file not found at {drum_stem_path} (Raw: {raw_path})")
            return None

        # Adicionar evento de início para feedback no UI
        await self._job_service.add_session_event(
            session_id,
            stage="drum_analysis",
            level="info",
            message="Iniciando análise técnica da bateria (ADTOF SOTA model)...",
            progress=0
        )

        try:
            analysis = await asyncio.to_thread(
                self._run_analysis, drum_stem_path, session_id
            )
            self._persist_analysis(session_id, analysis)
            
            # Adicionar evento de conclusão
            await self._job_service.add_session_event(
                session_id,
                stage="drum_analysis",
                level="info",
                message="Análise técnica da bateria concluída com sucesso.",
                progress=100
            )
            
            return analysis
        except Exception as e:
            logger.error(f"Drum analysis failed for {session_id}: {e}")
            await self._job_service.add_session_event(
                session_id,
                stage="drum_analysis",
                level="error",
                message=f"Falha na análise da bateria: {str(e)}",
                progress=0
            )
            raise

    @staticmethod
    def _run_analysis(stem_path: Path, session_id: str) -> DrumAnalysis:
        logger.info(f"Starting drum analysis for session {session_id} using ADTOF SOTA model")
        
        # 1. Caminhos de saída
        output_midi = settings.stems_root / session_id / "drum_transcription.mid"
        output_midi.parent.mkdir(parents=True, exist_ok=True)

        # 2. Transcrição via ADTOF (Deep Learning)
        try:
            from adtof_pytorch import transcribe_to_midi
            logger.info("Running ADTOF transcription...")
            transcribe_to_midi(str(stem_path), str(output_midi))
        except ImportError:
            logger.error("adtof_pytorch not installed. Please install it to use SOTA drum transcription.")
            raise RuntimeError("Drum transcription engine missing")
        except Exception as e:
            logger.error(f"Error during ADTOF transcription: {e}")
            raise

        # 3. Carregar MIDI gerado para extrair os hits
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(str(output_midi))
        
        # Mapeamento MIDI -> Tipo de peça do app
        PITCH_MAP = {
            35: "kick", 36: "kick",
            38: "snare", 40: "snare",
            42: "hihat", 44: "hihat", 46: "hihat",
            45: "tom", 47: "tom", 48: "tom", 50: "tom",
            49: "cymbal", 51: "cymbal", 52: "cymbal", 53: "cymbal", 55: "cymbal", 57: "cymbal"
        }

        hits = []
        for instrument in pm.instruments:
            for note in instrument.notes:
                hit_type = PITCH_MAP.get(note.pitch, "kick")
                hits.append(DrumHit(
                    time=float(note.start),
                    type=hit_type,
                    velocity=float(note.velocity / 127.0),
                    confidence=1.0 # ADTOF não exporta prob no MIDI
                ))
        
        # Ordenar por tempo
        hits.sort(key=lambda x: x.time)

        # 4. Análise rítmica (BPM e Beats) via Librosa
        # Carregamos o áudio (sr=22050 é suficiente e rápido)
        y, sr = librosa.load(str(stem_path), sr=22050)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if isinstance(tempo, (np.ndarray, list)) else float(tempo)
        
        # Refinamento de BPM via Hits (especialmente útil para stems de bateria)
        if len(hits) > 20:
            try:
                kick_times = np.array([h.time for h in hits if h.type == 'kick'])
                if len(kick_times) > 10:
                    diffs = np.diff(kick_times)
                    # Filtrar intervalos plausíveis para beats ou colcheias (0.2s a 0.8s)
                    valid_diffs = diffs[(diffs > 0.2) & (diffs < 0.8)]
                    if len(valid_diffs) > 5:
                        refined_avg_diff = np.median(valid_diffs)
                        refined_bpm = 60.0 / refined_avg_diff
                        # Se estiver muito longe do Librosa, pode ser uma subdivisão (dobro/metade)
                        if abs(refined_bpm - bpm) < 10:
                            bpm = refined_bpm
                        elif abs(refined_bpm*2 - bpm) < 5:
                            bpm = refined_bpm * 2
                        elif abs(refined_bpm/2 - bpm) < 5:
                            bpm = refined_bpm / 2
            except Exception as e:
                logger.warning(f"Failed to refine BPM via hits: {e}")

        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        
        # Alinhamento de Fase: Ajustar o primeiro beat para coincidir com o primeiro Kick forte
        if len(hits) > 0 and len(beat_times) > 0:
            first_kick = next((h for h in hits if h.type == 'kick' and h.velocity > 0.5), hits[0])
            offset = first_kick.time - beat_times[0]
            # Se o offset for significativo, deslocamos a grade inteira
            if abs(offset) < (60.0 / bpm): # Não deslocar mais que um beat
                beat_times = [t + offset for t in beat_times]

        duration = float(librosa.get_duration(y=y, sr=sr))

        analysis = DrumAnalysis(
            bpm=round(bpm, 1),
            time_signature="4/4",
            duration_seconds=round(duration, 2),
            beat_count=len(beat_times),
            beats=beat_times,
            hits=hits,
            analyzed_at=datetime.utcnow(),
            status="complete",
        )

        # 5. Extração de Padrões (Fase 3)
        try:
            from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase
            extractor = ExtractGroovePatternsUseCase()
            analysis.patterns = extractor.execute(analysis)
            logger.info(f"Identified {len(analysis.patterns)} groove patterns for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to extract groove patterns: {e}")

        return analysis


    @staticmethod
    def _persist_analysis(session_id: str, analysis: DrumAnalysis) -> None:
        """Salva resultado em JSON junto à sessão para evitar reprocessamento."""
        output_path = settings.stems_root / session_id / "drum_analysis.json"
        output_path.write_text(analysis.model_dump_json(indent=2))
        logger.info(f"Saved drum analysis for session {session_id} to {output_path}")

    @staticmethod
    def load_saved_analysis(session_id: str) -> Optional[DrumAnalysis]:
        """Carrega análise salva anteriormente, se existir."""
        path = settings.stems_root / session_id / "drum_analysis.json"
        if not path.is_file():
            return None
        try:
            return DrumAnalysis.model_validate_json(path.read_text())
        except Exception as e:
            logger.error(f"Error loading saved analysis for {session_id}: {e}")
            return None


def _estimate_time_signature(beat_times: list[float]) -> str:
    """Estima compasso pelo agrupamento natural dos beats."""
    if len(beat_times) < 8:
        return "4/4"
    # Implementação simplificada na Fase 1 — sempre retorna 4/4
    # A Fase 3 pode refinar usando downbeat detection
    return "4/4"

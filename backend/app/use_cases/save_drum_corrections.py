import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.drum_analysis import DrumAnalysis, DrumCorrections
from app.settings import settings

logger = logging.getLogger(__name__)

class SaveDrumCorrectionsUseCase:
    def __init__(self, job_service: object):
        self._job_service = job_service

    async def execute(self, session_id: str, corrections: DrumCorrections) -> Optional[DrumAnalysis]:
        job = await self._job_service.get_job(session_id)
        if job is None:
            logger.warning(f"Job not found for session {session_id}")
            return None

        # Carregar análise original para manter BPM/Beats etc
        from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
        analysis = AnalyzeDrumStemUseCase.load_saved_analysis(session_id)
        
        if analysis is None:
            # Se não existe análise, não podemos corrigir algo que não existe (ou deveríamos criar uma básica?)
            # Para simplificar, assumimos que a análise deve existir.
            logger.warning(f"Cannot save corrections for session {session_id} without existing analysis")
            return None

        # Atualizar hits e marcar como corrigido
        analysis.hits = corrections.hits
        analysis.is_corrected = True
        analysis.analyzed_at = datetime.utcnow()

        # Recalcular padrões rítmicos baseados nas correções
        try:
            from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase
            extractor = ExtractGroovePatternsUseCase()
            analysis.patterns = extractor.execute(analysis)
            logger.info(f"Re-extracted {len(analysis.patterns)} groove patterns after manual correction for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to re-extract patterns after correction: {e}")

        # Persistir a análise atualizada
        self._persist_corrections(session_id, corrections)
        AnalyzeDrumStemUseCase._persist_analysis(session_id, analysis)
        
        return analysis

    def _persist_corrections(self, session_id: str, corrections: DrumCorrections) -> None:
        """Salva as correções em um arquivo separado para dataset de treino."""
        session_dir = settings.stems_root / session_id
        corrections_path = session_dir / "drum_corrections.json"
        
        # Podemos salvar como uma lista de revisões se quisermos
        import json
        history_path = session_dir / "drum_corrections_history.jsonl"
        
        with open(history_path, "a") as f:
            f.write(corrections.model_dump_json() + "\n")
            
        # Salva o mais recente
        corrections_path.write_text(corrections.model_dump_json(indent=2))
        logger.info(f"Saved drum corrections for session {session_id}")

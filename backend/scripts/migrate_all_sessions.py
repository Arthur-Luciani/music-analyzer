import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Adicionar o diretório backend ao path para importar as apps
sys.path.append(str(Path(__file__).parent.parent))

from app.settings import settings
from app.services.jobs import job_service
from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase
from app.use_cases.extract_drum_samples import ExtractDrumSamplesUseCase
from app.models.drum_analysis import DrumAnalysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migration")

async def migrate_session(session_id: str, stems_root: Path):
    session_path = stems_root / session_id
    drum_stem = session_path / "drums.mp3"
    
    if not drum_stem.exists():
        # Fallback para drums.wav
        drum_stem = session_path / "drums.wav"
        if not drum_stem.exists():
            logger.warning(f"Sesso {session_id} ignorada (sem udio de bateria)")
            return

    analysis_file = session_path / "drum_analysis.json"
    analysis = None

    # 1. Carregar ou criar anlise base
    if analysis_file.exists():
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis = DrumAnalysis.model_validate_json(f.read())
        except Exception as e:
            logger.error(f"Erro ao ler anlise da sesso {session_id}: {e}")

    # 2. Executar Anlise de Bateria se faltar hits
    if not analysis or not analysis.hits:
        logger.info(f"Sesso {session_id}: Executando anlise ADTOF completa...")
        use_case = AnalyzeDrumStemUseCase(job_service)
        analysis = await use_case.execute(session_id)
    
    if not analysis:
        logger.error(f"Sesso {session_id}: Falha ao obter anlise.")
        return

    # 3. Extrair Padres de Groove se faltar
    if not analysis.patterns:
        logger.info(f"Sesso {session_id}: Extraindo padres de groove...")
        pattern_extractor = ExtractGroovePatternsUseCase()
        analysis.patterns = pattern_extractor.execute(analysis)

    # 4. Extrair Samples de udio (HQ)
    logger.info(f"Sesso {session_id}: Extraindo samples de udio de alta qualidade...")
    sample_extractor = ExtractDrumSamplesUseCase(stems_root)
    await sample_extractor.execute(session_id, analysis)

    # 5. Salvar resultado final
    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write(analysis.model_dump_json(indent=2))
    
    logger.info(f"Sesso {session_id}: MIGRADA COM SUCESSO.")

async def main():
    stems_root = settings.storage_root / "stems"
    if not stems_root.exists():
        logger.error(f"Diretório de stems não encontrado: {stems_root}")
        return

    sessions = [d.name for d in stems_root.iterdir() if d.is_dir()]
    logger.info(f"Iniciando migração de {len(sessions)} sessões...")

    for session_id in sessions:
        try:
            await migrate_session(session_id, stems_root)
        except Exception as e:
            logger.error(f"Falha catastrófica na migração da sessão {session_id}: {e}")

if __name__ == "__main__":
    asyncio.run(main())

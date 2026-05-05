
import json
from pathlib import Path
import sys
import os

# Adicionar backend ao path para importar as classes
sys.path.append(os.getcwd())

from app.models.drum_analysis import DrumAnalysis
from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase

session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")

if path.exists():
    analysis = DrumAnalysis.model_validate_json(path.read_text())
    extractor = ExtractGroovePatternsUseCase()
    analysis.patterns = extractor.execute(analysis)
    
    # Salvar de volta
    path.write_text(analysis.model_dump_json(indent=2))
    print(f"Session {session_id} updated with {len(analysis.patterns)} patterns.")
    for p in analysis.patterns:
        print(f" - {p.name}: {p.frequency} times")
else:
    print("File not found")

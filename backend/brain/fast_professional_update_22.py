
import sys
import os
sys.path.append(os.getcwd())

from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase
from app.models.drum_analysis import DrumHit, DrumAnalysis
import json
from pathlib import Path
from datetime import datetime

def update_session_22_with_groovetoolbox():
    session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    
    # Reconstituir hits e beats
    hits = [DrumHit(**h) for h in data['hits']]
    beats = data['beats']
    
    # Criar um objeto de análise mockado
    analysis = DrumAnalysis(
        bpm=data['bpm'],
        duration_seconds=data['duration_seconds'],
        beat_count=len(beats),
        beats=beats,
        hits=hits,
        analyzed_at=datetime.fromisoformat(data['analyzed_at'])
    )
    
    # Rodar o novo extrator
    use_case = ExtractGroovePatternsUseCase()
    patterns = use_case.execute(analysis)
    
    # Atualizar o JSON
    data['patterns'] = [p.dict() for p in patterns]
    path.write_text(json.dumps(data, indent=2))
    
    print(f"Professional update complete for Session {session_id}")
    print(f"Grid used: {'Ternary (12)' if len(patterns[0].kick) == 12 else 'Binary (16)'}")
    print(f"Top Groove: {patterns[0].name} ({patterns[0].frequency} occ)")
    print(f"Syncopation Score: {patterns[0].score}")

if __name__ == "__main__":
    update_session_22_with_groovetoolbox()

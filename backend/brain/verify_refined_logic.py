
import sys
import os
sys.path.append(os.getcwd())

from app.use_cases.extract_groove_patterns import ExtractGroovePatternsUseCase
from app.models.drum_analysis import DrumHit
import json
from pathlib import Path

def test_extraction():
    session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    
    hits = [DrumHit(time=h['time'], type=h['type'], velocity=h['velocity']) for h in data['hits']]
    
    # IMPORTANTE: Vamos usar um grid de 125 BPM perfeito começando no primeiro kick (0.02s)
    # para simular o que o novo AnalyzeDrumStemUseCase faria.
    bpm = 124.82
    beat_dur = 60.0 / bpm
    first_kick = 0.02
    beats = [first_kick + i * beat_dur for i in range(200)]
    
    class MockAnalysis:
        def __init__(self, hits, beats):
            self.hits = hits
            self.beats = beats
    
    use_case = ExtractGroovePatternsUseCase()
    patterns = use_case.execute(MockAnalysis(hits, beats))
    
    print(f"Refined Patterns (with 125 BPM grid and Phase-Awareness):")
    for p in patterns:
        print(f"  {p.name}: {p.frequency} occ")
        print(f"    Kick:  {p.kick}")
        print(f"    Snare: {p.snare}")

test_extraction()

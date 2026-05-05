
from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
from app.infrastructure.storage_manager import StorageManager
import logging

logging.basicConfig(level=logging.INFO)

def re_analyze(session_id):
    use_case = AnalyzeDrumStemUseCase()
    result = use_case.execute(session_id)
    print(f"BPM: {result.bpm}")
    print(f"Total Patterns: {len(result.patterns)}")
    for p in result.patterns[:3]:
        print(f"  {p.name}: {p.frequency} occurrences (Kick: {p.kick}, Snare: {p.snare})")

re_analyze("549a3164-aac5-4013-b7dd-71c3c40fbe8b")


import sys
import os
sys.path.append(os.getcwd())

from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
from app.models.drum_analysis import DrumAnalysis
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)

class MockJobService:
    async def get_job(self, job_id):
        class Job:
            def __init__(self):
                self.session_id = job_id
                self.job_id = job_id
                self.stems = {"drums": "drums.wav"}
        return Job()

import asyncio

def run_test():
    session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
    use_case = AnalyzeDrumStemUseCase(MockJobService())
    
    from app.settings import settings
    print(f"Storage Dir: {settings.storage_root}")
    
    try:
        result = asyncio.run(use_case.execute(session_id))
        print(f"SUCCESS! BPM: {result.bpm:.2f}")
        print(f"Beats: {len(result.beats)}")
        print(f"Patterns found: {len(result.patterns)}")
        for p in result.patterns:
            print(f"  {p.name}: {p.frequency} occ (K: {p.kick}, S: {p.snare})")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()

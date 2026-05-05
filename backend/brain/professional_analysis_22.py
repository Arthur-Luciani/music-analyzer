
import sys
import os
sys.path.append(os.getcwd())

from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
from app.models.drum_analysis import DrumAnalysis
import json
from pathlib import Path
import logging
import asyncio

logging.basicConfig(level=logging.INFO)

class MockJobService:
    async def get_job(self, job_id):
        class Job:
            def __init__(self):
                self.session_id = job_id
                self.job_id = job_id
                # Apontar para o arquivo real de bateria da sessão 22
                self.stems = {"drums": f"c:/git/music-analyzer/storage/stems/{job_id}/drums.mp3"}
        return Job()
    
    def __getattr__(self, name):
        async def mock_async_method(*args, **kwargs):
            return None
        return mock_async_method

async def run_professional_analysis():
    session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
    use_case = AnalyzeDrumStemUseCase(MockJobService())
    
    try:
        print("Starting Professional Groove Analysis (GrooveToolbox logic)...")
        result = await use_case.execute(session_id)
        
        # Salvar manualmente o resultado no arquivo da sessão
        path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
        # Converter para dict e salvar
        data = result.dict()
        # Resolver problemas de datetime no JSON
        data['analyzed_at'] = data['analyzed_at'].isoformat()
        path.write_text(json.dumps(data, indent=2))
        
        print(f"SUCCESS! BPM: {result.bpm:.2f}")
        print(f"Main Groove Frequency: {result.patterns[0].frequency}")
        print(f"Main Groove Complexity Score: {result.patterns[0].score}")
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_professional_analysis())

import sys
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path.cwd() / "backend"))

import asyncio
from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
from unittest.mock import MagicMock

async def test_analysis():
    # Mock job service
    job_service = MagicMock()
    
    # Session ID from previous ls
    session_id = "d7b9932e-f9f9-401a-9cf0-5f5e32bdcf97"
    drum_path = Path.cwd() / "storage" / "stems" / session_id / "drums.mp3"
    
    job = MagicMock()
    job.stems = {"drums": str(drum_path)}
    job_service.get_job = MagicMock(return_value=asyncio.Future())
    job_service.get_job.return_value.set_result(job)
    
    use_case = AnalyzeDrumStemUseCase(_job_service=job_service)
    
    print(f"Analyzing {drum_path}...")
    analysis = await use_case.execute(session_id)
    
    if analysis:
        print(f"Analysis successful!")
        print(f"BPM: {analysis.bpm}")
        print(f"Hits detected: {len(analysis.hits)}")
        if analysis.hits:
            print(f"First hit: {analysis.hits[0]}")
    else:
        print("Analysis failed.")

if __name__ == "__main__":
    asyncio.run(test_analysis())

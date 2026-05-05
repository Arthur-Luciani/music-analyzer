
import json
from pathlib import Path
import numpy as np

def estimate_bpm_from_hits(session_id):
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    hits = [h['time'] for h in data['hits'] if h['type'] == 'kick']
    
    if len(hits) < 10:
        return None
        
    diffs = np.diff(hits)
    # Filtrar intervalos que pareçam beats ou subdivisões (0.2s a 1.0s)
    # 125 BPM = 0.48s. 62.5 BPM = 0.96s.
    valid_diffs = diffs[(diffs > 0.3) & (diffs < 0.7)]
    
    if len(valid_diffs) == 0:
        return None
        
    avg_diff = np.median(valid_diffs)
    bpm = 60.0 / avg_diff
    
    # Se der algo perto de 62.5, dobra
    if 60 <= bpm <= 65: bpm *= 2
    
    return bpm

print(f"Estimated BPM from Kick hits: {estimate_bpm_from_hits('549a3164-aac5-4013-b7dd-71c3c40fbe8b'):.2f}")


import json
from pathlib import Path

def find_boom_boom_clap(session_id):
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    hits = data['hits']
    beats = data['beats']
    
    # Vamos tentar encontrar o padrão: Kick(1), Kick(2), Snare(3)
    # A 125 BPM, 1 beat = 0.48s.
    
    found_bars = []
    for i in range(len(beats) - 4):
        b1, b2, b3, b4, b5 = beats[i:i+5]
        
        # Check if there's a Kick near b1, Kick near b2, Snare near b3
        k1 = any(h for h in hits if abs(h['time'] - b1) < 0.1 and h['type'] == 'kick')
        k2 = any(h for h in hits if abs(h['time'] - b2) < 0.1 and h['type'] == 'kick')
        s3 = any(h for h in hits if abs(h['time'] - b3) < 0.1 and h['type'] == 'snare')
        
        if k1 and k2 and s3:
            found_bars.append(i)
            
    print(f"Found Boom-Boom-Clap at beat indices: {found_bars[:20]}")
    if found_bars:
        # Check the phase (index % 4)
        phases = [idx % 4 for idx in found_bars]
        from collections import Counter
        print(f"Phase distribution: {Counter(phases)}")

find_boom_boom_clap("549a3164-aac5-4013-b7dd-71c3c40fbe8b")

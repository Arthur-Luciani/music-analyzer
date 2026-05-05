
import json
from pathlib import Path
from collections import Counter
import numpy as np

def test_12_slots(session_id):
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    hits = data['hits']
    beats = data['beats']
    
    # Vamos testar um grid de 12 slots (3 por beat)
    # 4 beats * 3 = 12 slots
    
    phase_results = []
    for offset in range(4):
        bars = []
        num_bars = (len(beats) - offset) // 4
        for b_idx in range(num_bars):
            start_idx = offset + b_idx * 4
            end_idx = start_idx + 4
            if end_idx >= len(beats): break
            
            b_start = beats[start_idx]
            b_end = beats[end_idx]
            div = (b_end - b_start) / 12
            
            k, s = [0]*12, [0]*12
            for hit in hits:
                if b_start <= hit['time'] < b_end:
                    idx = int((hit['time'] - b_start + (div/2)) // div)
                    if idx >= 12: idx = 11
                    if hit['type'] == 'kick': k[idx] = 1
                    elif hit['type'] == 'snare': s[idx] = 1
            bars.append("".join(map(str, k)) + "|" + "".join(map(str, s)))
            
        counts = Counter(bars)
        if counts:
            pattern, freq = counts.most_common(1)[0]
            # Score: Kick no 0 e 1, Snare no 2? (Believer: 1-2-3 feel)
            # Slots: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
            # Beat 1: 0, 1, 2. Beat 2: 3, 4, 5...
            score = freq
            if pattern.startswith("111") or pattern.startswith("110"): score += 10
            
            phase_results.append({"offset": offset, "freq": freq, "pattern": pattern, "score": score})
            
    for r in sorted(phase_results, key=lambda x: x['score'], reverse=True):
        print(f"Offset {r['offset']}: Freq {r['freq']}, Pattern {r['pattern']}")

test_12_slots("549a3164-aac5-4013-b7dd-71c3c40fbe8b")


import json
from pathlib import Path
from collections import Counter

def analyze_phase(session_id):
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    if not path.exists():
        print("File not found")
        return
        
    data = json.loads(path.read_text())
    hits = data['hits']
    beats = data['beats']
    
    # Vamos tentar 4 offsets de beat (0, 1, 2, 3)
    results = []
    
    for offset in range(4):
        bars = []
        # Começar do beat 'offset'
        num_possible_bars = (len(beats) - offset) // 4
        for b_idx in range(num_possible_bars):
            start_idx = offset + b_idx * 4
            end_idx = start_idx + 4
            
            if end_idx >= len(beats):
                continue
            bar_start = beats[start_idx]
            bar_end = beats[end_idx]
            bar_duration = bar_end - bar_start
            div = bar_duration / 16
            
            k = [0]*16
            s = [0]*16
            for hit in hits:
                if bar_start <= hit['time'] < bar_end:
                    rel = hit['time'] - bar_start
                    idx = int((rel + (div/2)) // div)
                    if idx >= 16: idx = 15
                    if hit['type'] == 'kick': k[idx] = 1
                    if hit['type'] == 'snare': s[idx] = 1
            
            bars.append("".join(map(str, k)) + "|" + "".join(map(str, s)))
            
        counts = Counter(bars)
        most_common = counts.most_common(1)
        if most_common:
            pattern, freq = most_common[0]
            # Calcular "Standardness Score" (Kick no 1, Snare no 5/13)
            # Slots: 0 (Beat 1), 4 (Beat 2), 8 (Beat 3), 12 (Beat 4)
            k_bits, s_bits = pattern.split('|')
            score = 0
            if k_bits[0] == '1': score += 10 # Kick no 1
            if s_bits[4] == '1': score += 5  # Snare no 2
            if s_bits[12] == '1': score += 5 # Snare no 4
            
            results.append({
                "offset": offset,
                "freq": freq,
                "score": score,
                "pattern": pattern
            })
            
    # Ordenar por Score e depois Frequência
    results.sort(key=lambda x: (x['score'], x['freq']), reverse=True)
    
    for r in results:
        print(f"Offset {r['offset']}: Freq {r['freq']}, Score {r['score']}, Pattern {r['pattern']}")

analyze_phase("549a3164-aac5-4013-b7dd-71c3c40fbe8b")


import json
from pathlib import Path
from collections import Counter
import numpy as np

# Mocking the models needed for the UseCase logic if I were to use it, 
# but I'll just implement the logic here to be safe and fast.

def update_analysis(session_id):
    path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
    data = json.loads(path.read_text())
    
    hits_data = data['hits']
    # 1. Refinar BPM
    kick_times = np.array([h['time'] for h in hits_data if h['type'] == 'kick'])
    bpm = data['bpm']
    if len(kick_times) > 10:
        diffs = np.diff(kick_times)
        valid_diffs = diffs[(diffs > 0.2) & (diffs < 0.8)]
        if len(valid_diffs) > 5:
            refined_bpm = 60.0 / np.median(valid_diffs)
            if abs(refined_bpm - bpm) < 10: bpm = refined_bpm
            elif abs(refined_bpm*2 - bpm) < 5: bpm = refined_bpm * 2
            elif abs(refined_bpm/2 - bpm) < 5: bpm = refined_bpm / 2
    
    data['bpm'] = round(bpm, 2)
    
    # 2. Re-gerar Beats alinhados
    beat_dur = 60.0 / bpm
    first_kick = kick_times[0] if len(kick_times) > 0 else 0
    # Alinhar o primeiro beat ao primeiro kick (com um offset de bar se necessário, mas aqui simplificamos)
    new_beats = [first_kick + i * beat_dur for i in range(int(data['duration_seconds'] / beat_dur) + 2)]
    data['beats'] = new_beats
    
    # 3. Extrair Grooves (Lógica de Fase e Grid)
    phase_results = []
    for slots in [16, 12]:
        for offset in range(4):
            bars = []
            num_bars = (len(new_beats) - offset) // 4
            for b_idx in range(num_bars):
                start_idx = offset + b_idx * 4
                end_idx = start_idx + 4
                if end_idx >= len(new_beats): break
                b_start, b_end = new_beats[start_idx], new_beats[end_idx]
                div = (b_end - b_start) / slots
                k, s, h, t = [0]*slots, [0]*slots, [0]*slots, [0]*slots
                for hit in hits_data:
                    if b_start <= hit['time'] < b_end:
                        idx = int((hit['time'] - b_start + (div/2)) // div)
                        if idx >= slots: idx = slots - 1
                        if hit['type'] == 'kick': k[idx] = 1
                        elif hit['type'] == 'snare': s[idx] = 1
                        elif hit['type'] in ['hihat', 'cymbal']: h[idx] = 1
                        elif hit['type'] in ['tom', 'other']: t[idx] = 1
                bars.append({"k": "".join(map(str, k)), "s": "".join(map(str, s)), "h": "".join(map(str, h)), "t": "".join(map(str, t))})
            
            if not bars: continue
            
            counts = Counter([f"{b['k']}|{b['s']}|{b['t']}" for b in bars])
            common_freq = counts.most_common(1)[0][1]
            
            snare_pos = [4, 12] if slots == 16 else [3, 9]
            musicality = sum(1 for b in bars if b['k'][0] == '1')
            musicality += sum(0.5 for b in bars if any(b['s'][p] == '1' for p in snare_pos))
            
            phase_results.append({"slots": slots, "offset": offset, "bars": bars, "score": common_freq + (musicality / len(bars) * 15)})
        
    best = max(phase_results, key=lambda x: x['score'])
    slots = best['slots']
    
    # 4. Agrupamento Fuzzy
    final_patterns = []
    seen_keys = {}
    tolerance = 2 if slots == 16 else 1
    for b in best['bars']:
        key = f"{b['k']}|{b['s']}|{b['h']}|{b['t']}"
        match = None
        for k in seen_keys:
            dist = sum(1 for c1, c2 in zip(key.replace('|',''), k.replace('|','')) if c1 != c2)
            if dist <= tolerance:
                match = k
                break
        target = match if match else key
        seen_keys[target] = seen_keys.get(target, 0) + 1
        
    sorted_patterns = sorted(seen_keys.items(), key=lambda x: x[1], reverse=True)
    
    data['patterns'] = []
    for i, (key, freq) in enumerate(sorted_patterns[:5]):
        k, s, h, t = key.split('|')
        data['patterns'].append({
            "name": f"Groove {'Principal' if i==0 else chr(65+i)}",
            "frequency": freq,
            "kick": k,
            "snare": s,
            "hihat": h,
            "tom": t,
            "is_main": i == 0,
            "score": 0.5
        })
        
    path.write_text(json.dumps(data, indent=2))
    print(f"Updated {session_id}. BPM: {data['bpm']}, Main Freq: {data['patterns'][0]['frequency']}")

update_analysis("549a3164-aac5-4013-b7dd-71c3c40fbe8b")

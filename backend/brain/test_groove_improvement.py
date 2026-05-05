
import json
from pathlib import Path
from collections import Counter
from typing import List, Dict

# Mock classes to match the app structure
class GroovePattern:
    def __init__(self, name, frequency, score, kick, snare, hihat, is_main=False):
        self.name = name
        self.frequency = frequency
        self.score = score
        self.kick = kick
        self.snare = snare
        self.hihat = hihat
        self.is_main = is_main

    def to_dict(self):
        return {
            "name": self.name,
            "frequency": self.frequency,
            "score": self.score,
            "kick": self.kick,
            "snare": self.snare,
            "hihat": self.hihat,
            "is_main": self.is_main
        }

class ImprovedGrooveExtractor:
    def execute(self, analysis_data: dict, beats_per_bar: int = 4) -> List[dict]:
        hits = analysis_data.get('hits', [])
        beats = analysis_data.get('beats', [])
        
        if not hits or not beats:
            return []

        # Agrupar beats em compassos
        num_bars = len(beats) // beats_per_bar
        bars_data = []

        for b_idx in range(num_bars):
            start_beat_idx = b_idx * beats_per_bar
            end_beat_idx = start_beat_idx + beats_per_bar
            
            if end_beat_idx >= len(beats):
                break
                
            bar_start = beats[start_beat_idx]
            bar_end = beats[end_beat_idx]
            bar_duration = bar_end - bar_start
            
            # 16 divisões por compasso
            div_duration = bar_duration / 16
            
            bar_hits = {
                'kick': [0] * 16,
                'snare': [0] * 16,
                'hihat': [0] * 16,
            }
            
            # Encontrar hits que caem neste compasso
            for hit in hits:
                hit_time = hit['time']
                if bar_start <= hit_time < bar_end:
                    rel_time = hit_time - bar_start
                    div_idx = int((rel_time + (div_duration / 2)) // div_duration)
                    if div_idx >= 16: div_idx = 15
                    
                    h_type = hit['type']
                    if h_type in bar_hits:
                        bar_hits[h_type][div_idx] = 1
            
            bars_data.append(bar_hits)

        # Contar frequências com Fuzzy Matching (Hamming Distance < 2)
        patterns = []
        for bar in bars_data:
            k = "".join(map(str, bar['kick']))
            s = "".join(map(str, bar['snare']))
            h = "".join(map(str, bar['hihat']))
            key = f"{k}|{s}|{h}"
            
            found = False
            for p in patterns:
                if self._hamming_distance(p['key'], key) <= 2: # Tolerância de 2 bits
                    p['count'] += 1
                    found = True
                    break
            
            if not found:
                patterns.append({
                    'key': key,
                    'count': 1,
                    'kick': k,
                    'snare': s,
                    'hihat': h
                })

        # Ignorar silêncio
        patterns = [p for p in patterns if p['key'] != "0"*16+"|"+"0"*16+"|"+"0"*16]
        
        # Ordenar e formatar
        sorted_patterns = sorted(patterns, key=lambda x: x['count'], reverse=True)
        
        results = []
        for i, p in enumerate(sorted_patterns[:3]):
            results.append(GroovePattern(
                name=f"Groove {'Principal' if i == 0 else chr(65 + i)}",
                frequency=p['count'],
                score=self._calculate_complexity(p),
                kick=p['kick'],
                snare=p['snare'],
                hihat=p['hihat'],
                is_main=(i == 0)
            ).to_dict())
            
        return results

    def _hamming_distance(self, s1: str, s2: str) -> int:
        return sum(c1 != c2 for c1, c2 in zip(s1, s2))

    def _calculate_complexity(self, p: dict) -> float:
        all_bits = p['kick'] + p['snare'] + p['hihat']
        return round(all_bits.count('1') / 16.0, 2)

# Testar com o arquivo real da sessão 22
session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
path = Path(f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json")
if path.exists():
    data = json.loads(path.read_text())
    extractor = ImprovedGrooveExtractor()
    new_patterns = extractor.execute(data)
    print(json.dumps(new_patterns, indent=2))
else:
    print("File not found")

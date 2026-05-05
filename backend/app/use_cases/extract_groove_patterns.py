import logging
from collections import Counter
from typing import List
from app.models.drum_analysis import DrumAnalysis, DrumHit, GroovePattern

logger = logging.getLogger(__name__)

class ExtractGroovePatternsUseCase:
    def execute(self, analysis: DrumAnalysis, beats_per_bar: int = 4) -> List[GroovePattern]:
        """
        Identifica os padrões rítmicos mais frequentes na análise de forma robusta.
        Usa os beats detectados para evitar drift de tempo e Hamming distance para fuzzy matching.
        """
        if not analysis.hits or not analysis.beats:
            return []

        hits = analysis.hits
        beats = analysis.beats
              
        # 1. Extração de candidatos por compasso
        # Vamos testar 4 possíveis "fases" e 2 tipos de grid (16 slots e 12 slots para tercinados)
        grid_types = [16, 12]
        best_overall_phase = None
        
        for slots in grid_types:
            for offset in range(4):
                bar_candidates = []
                num_bars = (len(beats) - offset) // 4
                
                for b_idx in range(num_bars):
                    start_idx = offset + b_idx * 4
                    end_idx = start_idx + 4
                    if end_idx >= len(beats): break
                    
                    bar_start = beats[start_idx]
                    bar_end = beats[end_idx]
                    bar_duration = bar_end - bar_start
                    div = bar_duration / slots
                    
                    # Gerar bitmasks para Kick, Snare, HiHat e Tom
                    k, s, h, t = [0]*slots, [0]*slots, [0]*slots, [0]*slots
                    
                    for hit in hits:
                        if bar_start <= hit.time < bar_end:
                            rel = hit.time - bar_start
                            slot = int((rel + (div/2)) // div)
                            if slot >= slots: slot = slots - 1
                            
                            if hit.type == "kick": k[slot] = 1
                            elif hit.type == "snare": s[slot] = 1
                            elif hit.type in ["hihat", "cymbal"]: h[slot] = 1
                            elif hit.type in ["tom", "other"]: t[slot] = 1
                    
                    bar_candidates.append({
                        "kick": "".join(map(str, k)),
                        "snare": "".join(map(str, s)),
                        "hihat": "".join(map(str, h)),
                        "tom": "".join(map(str, t))
                    })
                
                if not bar_candidates: continue

                # Avaliar esta fase/grid:
                patterns_str = [f"{b['kick']}|{b['snare']}|{b['tom']}" for b in bar_candidates]
                counts = Counter(patterns_str)
                most_common_freq = counts.most_common(1)[0][1] if counts else 0
                
                # Score de "Musicalidade": Kick no slot 0, Snare no slot 4/12 (ou 3/9 em grid 12)
                musicality = 0
                snare_beat_2 = 4 if slots == 16 else 3
                snare_beat_4 = 12 if slots == 16 else 9
                
                for b in bar_candidates:
                    if b['kick'][0] == '1': musicality += 1
                    if b['snare'][snare_beat_2] == '1': musicality += 0.5
                    if b['snare'][snare_beat_4] == '1': musicality += 0.5
                    # Em "Believer", o Tom é essencial
                    if b['tom'][0] == '1' or b['tom'][1] == '1': musicality += 0.3
                
                score = most_common_freq + (musicality / len(bar_candidates) * 15)
                
                if best_overall_phase is None or score > best_overall_phase["score"]:
                    best_overall_phase = {
                        "offset": offset,
                        "slots": slots,
                        "candidates": bar_candidates,
                        "score": score
                    }

        if not best_overall_phase:
            return []
            
        bars_data = best_overall_phase["candidates"]
        slots = best_overall_phase["slots"]

        # 2. Agrupamento Fuzzy (Inspirado no GrooveToolbox)
        from app.services.groove_toolbox_adapter import GrooveSimilarity, RhythmMetrics
        
        patterns_registry = []
        for bar in bars_data:
            k_bits = bar['kick']
            s_bits = bar['snare']
            h_bits = bar['hihat']
            t_bits = bar['tom']
            key = f"{k_bits}|{s_bits}|{h_bits}|{t_bits}"
            
            found = False
            # Tolerância adaptativa baseada em fuzzy Hamming distance
            # Se a distância total (somando todas as peças) for pequena, agrupamos.
            for reg in patterns_registry:
                d_k = GrooveSimilarity.fuzzy_hamming_distance(k_bits, reg['kick'], slots)
                d_s = GrooveSimilarity.fuzzy_hamming_distance(s_bits, reg['snare'], slots)
                d_t = GrooveSimilarity.fuzzy_hamming_distance(t_bits, reg['tom'], slots)
                
                total_dist = d_k + d_s + d_t
                
                # Limiar de similaridade (ajustável)
                threshold = 1.5 if slots == 16 else 1.0
                
                if total_dist <= threshold:
                    reg['frequency'] += 1
                    found = True
                    break
            
            if not found:
                patterns_registry.append({
                    "key": key,
                    "frequency": 1,
                    "kick": k_bits,
                    "snare": s_bits,
                    "hihat": h_bits,
                    "tom": t_bits
                })

        # 3. Formatação final e Cálculo de Métricas Profissionais
        silence_key = ("0"*slots + "|") * 3 + "0"*slots
        patterns_registry = [p for p in patterns_registry if p['key'] != silence_key]
        
        patterns_registry.sort(key=lambda x: x['frequency'], reverse=True)
        
        results = []
        for i, reg in enumerate(patterns_registry[:5]):
            # Calcular syncopation combinada (Bumbo + Caixa)
            sync_k = RhythmMetrics.calculate_syncopation(reg['kick'], slots)
            sync_s = RhythmMetrics.calculate_syncopation(reg['snare'], slots)
            
            results.append(GroovePattern(
                name=f"Groove {'Principal' if i == 0 else chr(65 + i)}",
                frequency=reg['frequency'],
                score=round((sync_k + sync_s) * 5, 2), # Escala 0-10 aproximada
                kick=reg['kick'],
                snare=reg['snare'],
                hihat=reg['hihat'],
                tom=reg['tom'],
                is_main=(i == 0)
            ))
            
        return results

import logging
from pathlib import Path
import librosa
import soundfile as sf
import numpy as np
from app.models.drum_analysis import DrumAnalysis

logger = logging.getLogger(__name__)

class ExtractDrumSamplesUseCase:
    def __init__(self, stems_root: Path):
        self.stems_root = stems_root

    async def execute(self, session_id: str, analysis: DrumAnalysis) -> dict:
        """
        Extrai amostras de áudio (samples) para cada peça da bateria.
        Retorna um dicionário com os caminhos relativos dos arquivos gerados.
        """
        drum_stem_path = self.stems_root / session_id / "drums.mp3"
        if not drum_stem_path.exists():
            # Fallback para drums.wav se existir
            drum_stem_path = self.stems_root / session_id / "drums.wav"
            if not drum_stem_path.exists():
                logger.error(f"Drum stem not found for session {session_id}")
                return {}

        samples_dir = self.stems_root / session_id / "samples"
        samples_dir.mkdir(exist_ok=True)

        # Carregar áudio da bateria
        try:
            y, sr = librosa.load(str(drum_stem_path), sr=None)
        except Exception as e:
            logger.error(f"Error loading drum stem: {e}")
            return {}

        sample_paths = {}
        target_types = ['kick', 'snare', 'hihat']

        for drum_type in target_types:
            # Encontrar golpes isolados (sem outras peças tocando ao mesmo tempo)
            # para evitar bleed / ruído de outras peças no sample
            type_hits = [h for h in analysis.hits if h.type == drum_type]
            if not type_hits:
                continue

            # Tentar encontrar o golpe mais "puro"
            best_hit = None
            for hit in sorted(type_hits, key=lambda x: x.velocity, reverse=True):
                # Verificar se há outros hits próximos (janela de 60ms)
                others_nearby = [h for h in analysis.hits if h != hit and abs(h.time - hit.time) < 0.06]
                if not others_nearby:
                    best_hit = hit
                    break
            
            # Se não achou nenhum 100% isolado, pega o de maior velocidade
            if not best_hit:
                best_hit = type_hits[0]

            # Extrair sample (250ms é suficiente para transientes)
            start_sample = int(best_hit.time * sr)
            duration_samples = int(0.25 * sr) 
            end_sample = min(start_sample + duration_samples, len(y))

            sample_audio = y[start_sample:end_sample].copy()
            
            # Limpeza básica via filtragem simples (reduzir bleed)
            try:
                if drum_type == 'kick':
                    # LPF básico para o bumbo (remover brilho/chiado de pratos)
                    # Usando média móvel simples como filtro passa-baixa rudimentar mas eficaz para samples curtos
                    # se não quisermos complicar com filtros scipy
                    sample_audio = np.convolve(sample_audio, np.ones(5)/5, mode='same')
                elif drum_type == 'hihat':
                    # HPF básico (remover sub-graves/bumbo que vazou)
                    # Subtrair a média móvel para fazer um high-pass rudimentar
                    low_freq = np.convolve(sample_audio, np.ones(10)/10, mode='same')
                    sample_audio = sample_audio - low_freq
            except:
                pass # Se falhar o filtro, usa o bruto

            # Normalizar volume
            max_val = np.max(np.abs(sample_audio))
            if max_val > 0:
                sample_audio = sample_audio / max_val * 0.9

            # Aplicar fade-out suave para evitar clicks
            fade_len = int(0.1 * sr)
            if len(sample_audio) > fade_len:
                fade = np.exp(np.linspace(0, -5, fade_len)) # Fade logarítmico soa mais natural
                sample_audio[-fade_len:] *= fade

            sample_filename = f"{drum_type}.wav"
            sample_path = samples_dir / sample_filename
            
            sf.write(str(sample_path), sample_audio, sr)
            sample_paths[drum_type] = f"/api/sessions/{session_id}/samples/{sample_filename}"

        return sample_paths

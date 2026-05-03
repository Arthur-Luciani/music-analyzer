import pretty_midi
import json
import os
from datetime import datetime
import librosa
import numpy as np

# Configurações
session_id = "19fd5045-3ed7-4bd0-9c16-51c49e196b56"
midi_path = r"c:\git\music-analyzer\storage\exports\test_drum_transcription.mid"
audio_path = r"c:\git\music-analyzer\storage\stems\19fd5045-3ed7-4bd0-9c16-51c49e196b56\drums.mp3"
output_json = r"c:\git\music-analyzer\storage\stems\19fd5045-3ed7-4bd0-9c16-51c49e196b56\drum_analysis.json"

# Mapeamento MIDI -> Tipo de peça do app
PITCH_MAP = {
    35: "kick",
    36: "kick",
    38: "snare",
    40: "snare",
    42: "hihat",
    44: "hihat",
    46: "hihat",
    45: "tom",
    47: "tom",
    48: "tom",
    50: "tom",
    49: "cymbal",
    51: "cymbal",
    52: "cymbal",
    53: "cymbal",
    55: "cymbal",
    57: "cymbal"
}

print("Carregando MIDI...")
pm = pretty_midi.PrettyMIDI(midi_path)
hits = []

for instrument in pm.instruments:
    for note in instrument.notes:
        hit_type = PITCH_MAP.get(note.pitch, "kick") # default para kick se não mapeado
        hits.append({
            "time": float(note.start),
            "type": hit_type,
            "velocity": float(note.velocity / 127.0),
            "confidence": 1.0 # ADTOF-pytorch não exporta probabilidade no MIDI básico
        })

# Ordenar hits por tempo
hits.sort(key=lambda x: x["time"])

print("Processando áudio para obter beats (grade)...")
y, sr = librosa.load(audio_path, sr=22050)
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
# tempo can be a scalar or an array depending on version, handle both
bpm = float(tempo[0]) if isinstance(tempo, (np.ndarray, list)) else float(tempo)
beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

analysis = {
    "bpm": round(bpm, 1),
    "time_signature": "4/4",
    "duration_seconds": round(float(librosa.get_duration(y=y, sr=sr)), 2),
    "beat_count": len(beat_times),
    "beats": beat_times,
    "hits": hits,
    "analysis_version": "2.0-adtof",
    "analyzed_at": datetime.utcnow().isoformat(),
    "status": "complete",
    "is_corrected": False
}

print(f"Salvando análise em {output_json}...")
with open(output_json, "w") as f:
    json.dump(analysis, f, indent=2)

print("Sucesso! Agora você pode abrir o Drum Inspector para esta sessão.")

import os
import sys
import time
import json
import pretty_midi
import librosa
import numpy as np
from datetime import datetime
from adtof_pytorch import transcribe_to_midi

# Mapeamento MIDI -> Tipo de peça do app
PITCH_MAP = {
    35: "kick", 36: "kick",
    38: "snare", 40: "snare",
    42: "hihat", 44: "hihat", 46: "hihat",
    45: "tom", 47: "tom", 48: "tom", 50: "tom",
    49: "cymbal", 51: "cymbal", 52: "cymbal", 53: "cymbal", 55: "cymbal", 57: "cymbal"
}

def process_session(session_id):
    base_path = f"c:/git/music-analyzer/storage/stems/{session_id}"
    input_audio = os.path.join(base_path, "drums.mp3")
    output_midi = os.path.join(base_path, "adtof_transcription.mid")
    output_json = os.path.join(base_path, "drum_analysis.json")

    if not os.path.exists(input_audio):
        print(f"Erro: Arquivo {input_audio} nao encontrado.")
        return

    print(f"--- Processando Sessao: {session_id} ---")
    
    # 1. Transcrever para MIDI via ADTOF
    print("Iniciando ADTOF Transcription...")
    start_time = time.time()
    transcribe_to_midi(input_audio, output_midi)
    print(f"ADTOF concluido em {time.time() - start_time:.2f}s")

    # 2. Converter MIDI para nosso JSON
    print("Convertendo MIDI para JSON...")
    pm = pretty_midi.PrettyMIDI(output_midi)
    hits = []
    for instrument in pm.instruments:
        for note in instrument.notes:
            hits.append({
                "time": float(note.start),
                "type": PITCH_MAP.get(note.pitch, "kick"),
                "velocity": float(note.velocity / 127.0),
                "confidence": 1.0
            })
    hits.sort(key=lambda x: x["time"])

    # 3. Obter Beats para a grade
    print("Calculando Beats (Librosa)...")
    y, sr = librosa.load(input_audio, sr=22050)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
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
        "analyzed_at": datetime.now().isoformat(),
        "status": "complete",
        "is_corrected": False
    }

    with open(output_json, "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"Sucesso! Analise salva em {output_json}")

if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "918ea4a6-625e-4d75-83ab-50bfd7c89c20"
    process_session(sid)

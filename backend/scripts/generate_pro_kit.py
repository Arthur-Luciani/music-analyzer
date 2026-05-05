import numpy as np
import soundfile as sf
from pathlib import Path

def generate_kick(sr=44100):
    duration = 0.4
    t = np.linspace(0, duration, int(sr * duration))
    # Sine sweep from 150Hz to 30Hz
    freq = np.geomspace(150, 30, len(t))
    phase = 2 * np.pi * np.cumsum(freq) / sr
    kick = np.sin(phase)
    # Envelope
    env = np.exp(-12 * t)
    return kick * env

def generate_snare(sr=44100):
    duration = 0.3
    t = np.linspace(0, duration, int(sr * duration))
    # Noise + 200Hz sine
    noise = np.random.uniform(-1, 1, len(t))
    tone = np.sin(2 * np.pi * 200 * t)
    snare = 0.7 * noise + 0.3 * tone
    # Envelope
    env = np.exp(-15 * t)
    return snare * env

def generate_hihat(sr=44100):
    duration = 0.1
    t = np.linspace(0, duration, int(sr * duration))
    # White noise
    noise = np.random.uniform(-1, 1, len(t))
    # High pass filter (simple)
    hihat = noise - np.convolve(noise, np.ones(5)/5, mode='same')
    # Envelope
    env = np.exp(-40 * t)
    return hihat * env

def main():
    output_dir = Path("../frontend/public/assets/drums")
    output_dir.mkdir(parents=True, exist_ok=True)
    sr = 44100

    sf.write(output_dir / "kick_pro.wav", generate_kick(sr), sr)
    sf.write(output_dir / "snare_pro.wav", generate_snare(sr), sr)
    sf.write(output_dir / "hihat_pro.wav", generate_hihat(sr), sr)
    print(f"Pro Kit gerado em: {output_dir}")

if __name__ == "__main__":
    main()

import soundfile as sf
import numpy as np
from pathlib import Path

def check_file(path):
    data, sr = sf.read(str(path))
    max_val = np.max(np.abs(data))
    rms = np.sqrt(np.mean(data**2))
    print(f"File: {path.name}")
    print(f"Max Amplitude: {max_val}")
    print(f"RMS Energy: {rms}")
    if max_val == 0:
        print("ALERT: FILE IS COMPLETELY SILENT!")
    elif max_val < 0.001:
        print("WARNING: FILE IS VERY QUIET!")
    else:
        print("File seems to have content.")

test_file = Path("D:/drum_dataset/kick/enst_drummer_1_005_hits_bass-drum_pedal_x5_0.243_bd.wav")
if test_file.exists():
    check_file(test_file)
else:
    print("Test file not found.")

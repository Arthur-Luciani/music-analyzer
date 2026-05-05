
import pretty_midi
import json
from pathlib import Path

session_id = "549a3164-aac5-4013-b7dd-71c3c40fbe8b"
midi_path = f"c:/git/music-analyzer/storage/stems/{session_id}/drum_transcription.mid"
analysis_path = f"c:/git/music-analyzer/storage/stems/{session_id}/drum_analysis.json"

pm = pretty_midi.PrettyMIDI(midi_path)
print(f"Generated MIDI: {midi_path}")
print(f"Duration: {pm.get_end_time():.2f}s")
print(f"Total Notes: {sum(len(inst.notes) for inst in pm.instruments)}")

# Load analysis to check BPM/Beats
with open(analysis_path) as f:
    analysis = json.load(f)

print(f"Analysis BPM: {analysis['bpm']}")
print(f"Total Hits in Analysis: {len(analysis['hits'])}")

# Check first few hits alignment with beats
beats = analysis['beats']
hits = analysis['hits']

print("\nAlignment Check (First 5 hits):")
for i in range(min(5, len(hits))):
    h = hits[i]
    # Find nearest beat
    nearest_beat = min(beats, key=lambda x: abs(x - h['time']))
    diff = h['time'] - nearest_beat
    print(f"Hit {i}: {h['type']} at {h['time']:.3f}s (Nearest Beat: {nearest_beat:.3f}s, Offset: {diff:+.3f}s)")

# Check if hits are "jittery"
offsets = []
for h in hits:
    nearest_beat = min(beats, key=lambda x: abs(x - h['time']))
    offsets.append(h['time'] - nearest_beat)

avg_offset = sum(offsets) / len(offsets)
std_offset = (sum((x - avg_offset)**2 for x in offsets) / len(offsets))**0.5
print(f"\nAverage Offset from nearest beat: {avg_offset:+.4f}s")
print(f"Standard Deviation of offsets: {std_offset:.4f}s")

# If std_offset is high, it means the hits are not locked to the beats, 
# which might make the 16th note quantization fail if they land in the wrong bin.

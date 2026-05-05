
import pretty_midi
import json

def extract_hits_from_midi(midi_path):
    pm = pretty_midi.PrettyMIDI(midi_path)
    
    PITCH_MAP = {
        35: "kick", 36: "kick",
        38: "snare", 40: "snare",
        42: "hihat", 44: "hihat", 46: "hihat",
        45: "tom", 47: "tom", 48: "tom", 50: "tom",
        49: "cymbal", 51: "cymbal", 52: "cymbal", 53: "cymbal", 55: "cymbal", 57: "cymbal"
    }

    hits = []
    for instrument in pm.instruments:
        for note in instrument.notes:
            hit_type = PITCH_MAP.get(note.pitch, "kick")
            hits.append({
                "time": float(note.start),
                "type": hit_type,
                "velocity": float(note.velocity / 127.0)
            })
    
    hits.sort(key=lambda x: x["time"])
    return hits

# Inspect Reference MIDI
ref_midi = "c:/git/music-analyzer/prototypes/download.mid"
ref_hits = extract_hits_from_midi(ref_midi)

print(f"Reference MIDI Hits: {len(ref_hits)}")
print("First 10 hits:")
for h in ref_hits[:10]:
    print(f"  {h['time']:.3f}s - {h['type']} (vel: {h['velocity']:.2f})")

# Estimate BPM from ref hits if possible (simple interval average)
intervals = []
for i in range(len(ref_hits)-1):
    diff = ref_hits[i+1]['time'] - ref_hits[i]['time']
    if 0.2 < diff < 0.8: # Filter for typical beat divisions
        intervals.append(diff)

if intervals:
    avg_interval = sum(intervals) / len(intervals)
    # If 125 BPM, 1 beat = 0.48s. 1 16th = 0.12s.
    print(f"Avg small interval: {avg_interval:.3f}s")

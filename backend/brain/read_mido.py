
import mido

def read_mido(path):
    try:
        mid = mido.MidiFile(path)
        print(f"Mido tracks: {len(mid.tracks)}")
        for i, track in enumerate(mid.tracks):
            print(f"Track {i}: {len(track)} messages")
            for msg in track[:20]:
                print(f"  {msg}")
    except Exception as e:
        print(f"Error: {e}")

read_mido("c:/git/music-analyzer/prototypes/download.mid")

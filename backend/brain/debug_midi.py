
import pretty_midi

def debug_midi(midi_path):
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        print(f"File: {midi_path}")
        print(f"Duration: {pm.get_end_time():.2f}s")
        print(f"Instruments: {len(pm.instruments)}")
        for i, inst in enumerate(pm.instruments):
            print(f"  Inst {i}: {inst.name} (Program: {inst.program}, Is Drum: {inst.is_drum})")
            print(f"    Notes: {len(inst.notes)}")
            if len(inst.notes) > 0:
                pitches = sorted(list(set([n.pitch for n in inst.notes])))
                print(f"    Pitches: {pitches}")
    except Exception as e:
        print(f"Error: {e}")

debug_midi("c:/git/music-analyzer/prototypes/download.mid")

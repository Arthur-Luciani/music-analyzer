import pretty_midi
import collections

midi_path = r"c:\git\music-analyzer\storage\exports\test_drum_transcription.mid"

try:
    pm = pretty_midi.PrettyMIDI(midi_path)
    print(f"Arquivo MIDI carregado: {midi_path}")
    print(f"Duração total: {pm.get_end_time():.2f} segundos")
    
    # Contar instrumentos
    print(f"Número de instrumentos: {len(pm.instruments)}")
    
    for i, instrument in enumerate(pm.instruments):
        print(f"\nInstrumento {i}: {'Percussão' if instrument.is_drum else 'Melódico'}")
        print(f"Total de notas: {len(instrument.notes)}")
        
        # Estatísticas das notas (pitch)
        pitches = [note.pitch for note in instrument.notes]
        pitch_counts = collections.Counter(pitches)
        
        print("Distribuição de Peças (Notas MIDI):")
        # Mapeamento GM básico para referência
        gm_map = {36: "Kick", 38: "Snare", 42: "Hi-hat (Closed)", 45: "Tom", 49: "Cymbal"}
        
        for pitch in sorted(pitch_counts.keys()):
            label = gm_map.get(pitch, "Outro")
            print(f"  - Nota {pitch} ({label}): {pitch_counts[pitch]} batidas")
            
        # Verificar se há notas sobrepostas (polifonia)
        overlaps = 0
        sorted_notes = sorted(instrument.notes, key=lambda x: x.start)
        for j in range(len(sorted_notes) - 1):
            if sorted_notes[j+1].start < sorted_notes[j].end:
                # Na bateria, notas simultâneas começam no mesmo tempo
                if abs(sorted_notes[j+1].start - sorted_notes[j].start) < 0.01:
                    overlaps += 1
        
        print(f"\nNotas simultâneas detectadas: {overlaps}")
        if overlaps > 0:
            print("Resultado: O modelo detectou polifonia (múltiplas peças tocadas juntas) corretamente.")
        else:
            print("Resultado: Não foram detectadas notas simultâneas expressivas.")

except Exception as e:
    print(f"Erro ao ler o MIDI: {e}")

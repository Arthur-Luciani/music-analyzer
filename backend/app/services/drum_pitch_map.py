"""Mapeamento compartilhado entre pitches GM (General MIDI) de bateria e os
tipos de golpe usados internamente (kick/snare/hihat/tom/cymbal).

Extraído de `analyze_drum_stem.PITCH_MAP` e `generate_drum_midi.HIT_TO_MIDI_NOTE`
para evitar duas definições divergentes do mesmo mapeamento.
"""

GM_PITCH_TO_HIT_TYPE: dict[int, str] = {
    35: "kick", 36: "kick",
    38: "snare", 40: "snare",
    42: "hihat", 44: "hihat", 46: "hihat",
    45: "tom", 47: "tom", 48: "tom", 50: "tom",
    49: "cymbal", 51: "cymbal", 52: "cymbal", 53: "cymbal", 55: "cymbal", 57: "cymbal",
}

HIT_TYPE_TO_GM_PITCH: dict[str, int] = {
    "kick":   36,
    "snare":  38,
    "hihat":  42,
    "tom":    47,
    "cymbal": 49,
}

# Posição na pauta de bateria (5 linhas) por pitch GM: (displayStep, displayOctave, notehead).
# Segue a convenção padrão de notação de bateria (bumbo grave/abaixo da pauta,
# caixa na linha do meio, chimbal/pratos acima da pauta com cabeça em "x").
# Não é uma tabela "oficial" única — MIDIs de mercado variam — mas cobre os
# pitches GM de bateria mais comuns com posições distintas e legíveis.
# Usado apenas para exibição em partitura (MusicXML), não afeta MIDI/áudio.
GM_PITCH_TO_STAFF_POSITION: dict[int, tuple[str, int, str]] = {
    35: ("F", 4, "normal"),  # Acoustic Bass Drum
    36: ("F", 4, "normal"),  # Bass Drum 1
    37: ("C", 5, "x"),       # Side Stick
    38: ("C", 5, "normal"),  # Acoustic Snare
    39: ("E", 5, "x"),       # Hand Clap
    40: ("C", 5, "normal"),  # Electric Snare
    41: ("D", 4, "normal"),  # Low Floor Tom
    42: ("G", 5, "x"),       # Closed Hi-Hat
    43: ("E", 4, "normal"),  # High Floor Tom
    44: ("G", 5, "x"),       # Pedal Hi-Hat
    45: ("G", 4, "normal"),  # Low Tom
    46: ("G", 5, "x"),       # Open Hi-Hat
    47: ("A", 4, "normal"),  # Low-Mid Tom
    48: ("B", 4, "normal"),  # Hi-Mid Tom
    49: ("A", 5, "x"),       # Crash Cymbal 1
    50: ("D", 5, "normal"),  # High Tom
    51: ("F", 5, "x"),       # Ride Cymbal 1
    52: ("A", 5, "x"),       # Chinese Cymbal
    53: ("F", 5, "x"),       # Ride Bell
    54: ("E", 5, "x"),       # Tambourine
    55: ("A", 5, "x"),       # Splash Cymbal
    56: ("E", 5, "normal"),  # Cowbell
    57: ("A", 5, "x"),       # Crash Cymbal 2
    59: ("F", 5, "x"),       # Ride Cymbal 2
}

DEFAULT_STAFF_POSITION: tuple[str, int, str] = ("B", 4, "normal")


def get_staff_position(pitch: int) -> tuple[str, int, str]:
    return GM_PITCH_TO_STAFF_POSITION.get(pitch, DEFAULT_STAFF_POSITION)

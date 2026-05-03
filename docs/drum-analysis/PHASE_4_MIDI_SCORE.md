# Fase 4 — Geração de MIDI e MusicXML

**Duração**: 3–4 dias
**Objetivo**: Converter os hits classificados em arquivos MIDI e MusicXML para download
**Saída**: Endpoints para download de `.mid` e `.musicxml`; exportação integrando ao painel existente

---

## Contexto

Com hits classificados pela Fase 3, agora convertemos essa lista em formatos que bateristas e produtores realmente usam:

- **MIDI** (`.mid`): importável em qualquer DAW (Pro Tools, Logic, Ableton, Reaper). Permite reeditar, quantizar e substituir samples.
- **MusicXML** (`.musicxml`): importável em editores de partitura (MuseScore, Sibelius, Finale). Gera a partitura completa.

---

## General MIDI Drum Map

O padrão MIDI define que canal 10 é reservado para percussão, com cada nota representando um instrumento:

| Instrumento | Nota MIDI | Nota Musical |
|---|---|---|
| Bumbo (Kick) | 36 | C2 |
| Caixa (Snare) | 38 | D2 |
| Hi-Hat Fechado | 42 | F#2 |
| Hi-Hat Aberto | 46 | A#2 |
| Tom Alto | 50 | D3 |
| Tom Médio | 47 | B2 |
| Tom Baixo | 45 | A2 |
| Crash | 49 | C#3 |
| Ride | 51 | D#3 |

Nossa classificação (kick/snare/hihat/tom/cymbal) mapeia para notas MIDI assim:

```python
HIT_TO_MIDI_NOTE = {
    "kick":   36,
    "snare":  38,
    "hihat":  42,   # hi-hat fechado por padrão
    "tom":    47,   # tom médio por padrão
    "cymbal": 49,   # crash por padrão
}
```

---

## Dependências a Adicionar

```diff
# backend/requirements.pipeline.txt

 # v2 - Analise (pos-MVP)
 librosa>=0.10.2.post1
-# pretty-midi>=0.2.10 # Temporariamente desabilitado
+pretty-midi>=0.2.10
+music21>=9.1
```

Verificar compatibilidade com Python 3.13 antes de reativar `pretty_midi`. Se houver problema, usar `mido>=1.3` como alternativa para MIDI e `music21` apenas para MusicXML.

---

## Caso de Uso — Geração de MIDI

**`app/use_cases/generate_drum_midi.py`**

```python
import logging
from dataclasses import dataclass
from pathlib import Path

from app.models.drum_analysis import DrumAnalysis
from app.settings import settings

logger = logging.getLogger(__name__)

HIT_TO_MIDI_NOTE = {
    "kick":   36,
    "snare":  38,
    "hihat":  42,
    "tom":    47,
    "cymbal": 49,
}

MIDI_VELOCITY_SCALE = 127  # MIDI usa escala 0–127


@dataclass
class GenerateDrumMidiUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[Path]:
        """Gera arquivo MIDI a partir do DrumAnalysis salvo."""
        import asyncio
        analysis = await asyncio.to_thread(
            self._load_analysis, session_id
        )
        if analysis is None or not analysis.hits:
            return None

        output_path = settings.stems_root / session_id / "drum_transcription.mid"
        await asyncio.to_thread(
            self._write_midi, analysis, output_path
        )
        return output_path

    @staticmethod
    def _load_analysis(session_id: str) -> Optional[DrumAnalysis]:
        from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
        return AnalyzeDrumStemUseCase.load_saved_analysis(session_id)

    @staticmethod
    def _write_midi(analysis: DrumAnalysis, output_path: Path) -> None:
        import pretty_midi

        # Cria MIDI com BPM correto
        midi = pretty_midi.PrettyMIDI(initial_tempo=analysis.bpm)

        # Canal 9 = drums no padrão General MIDI (índice 0)
        drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

        for hit in analysis.hits:
            if hit.type == "unknown":
                continue

            note_number = HIT_TO_MIDI_NOTE.get(hit.type, 38)
            velocity = max(1, min(127, int(hit.velocity * MIDI_VELOCITY_SCALE)))

            # Cada golpe tem duração de 50ms no MIDI
            note = pretty_midi.Note(
                velocity=velocity,
                pitch=note_number,
                start=hit.time,
                end=hit.time + 0.05,
            )
            drums.notes.append(note)

        midi.instruments.append(drums)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        midi.write(str(output_path))
        logger.info("MIDI written to %s (%d notes)", output_path, len(drums.notes))
```

---

## Geração de MusicXML

A conversão de MIDI para MusicXML é feita pelo `music21`, que cuida de:
- Quantização automática para grade rítmica (colcheias, semicolcheias)
- Mapeamento das notas MIDI para símbolos corretos de percussão
- Exportação no formato padrão que todos os editores de partitura entendem

```python
# Dentro de GenerateDrumMidiUseCase

@staticmethod
def _write_musicxml(midi_path: Path, output_path: Path) -> None:
    from music21 import converter, stream, midi as m21midi

    # Carregar o MIDI gerado
    score = converter.parse(str(midi_path))

    # Exportar como MusicXML
    score.write("musicxml", fp=str(output_path))
    logger.info("MusicXML written to %s", output_path)
```

---

## Quantização

Partituras geradas de áudio sem quantização ficam ilegíveis — cada nota cai em posições "quebradas" (ex: 0.503 segundos). Precisamos encaixar cada golpe na subdivisão rítmica mais próxima antes de gerar o MusicXML.

```python
def quantize_hits(hits: list[DrumHit], bpm: float, grid: str = "16") -> list[DrumHit]:
    """
    Encaixa cada hit na subdivisão mais próxima.

    grid="16" significa semicolcheias (1/16 de compasso em 4/4)
    """
    beat_duration = 60.0 / bpm         # duração de um beat em segundos
    grid_duration = beat_duration / (int(grid) / 4)  # duração da subdivisão

    quantized = []
    for hit in hits:
        # Arredondar para o grid mais próximo
        grid_position = round(hit.time / grid_duration)
        quantized_time = grid_position * grid_duration
        quantized.append(hit.model_copy(update={"time": quantized_time}))

    return quantized
```

---

## Novos Endpoints

```python
# main.py

@app.get("/api/sessions/{session_id}/drum-analysis/midi")
async def download_drum_midi(session_id: str):
    """Download do arquivo MIDI da transcrição de bateria."""
    use_case = GenerateDrumMidiUseCase(job_service)
    path = await use_case.execute(session_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="MIDI not available. Run drum analysis first.")
    return FileResponse(
        path=str(path),
        media_type="audio/midi",
        filename=f"drums_{session_id[:8]}.mid",
    )


@app.get("/api/sessions/{session_id}/drum-analysis/musicxml")
async def download_drum_musicxml(session_id: str):
    """Download do MusicXML para editar em MuseScore."""
    # Gerar MIDI primeiro se necessário, então converter para MusicXML
    ...
    return FileResponse(
        path=str(path),
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"drums_{session_id[:8]}.musicxml",
    )
```

---

## Frontend — Botões de Download

No `WorkspacePage.jsx`, dentro do painel de análise de bateria:

```jsx
<div className="drum-exports">
  <h4>Exportar Transcrição</h4>
  <a
    href={`/api/sessions/${sessionId}/drum-analysis/midi`}
    download
    className="btn btn-subtle"
  >
    ↓ MIDI (.mid)
  </a>
  <a
    href={`/api/sessions/${sessionId}/drum-analysis/musicxml`}
    download
    className="btn btn-subtle"
  >
    ↓ Partitura (.musicxml)
  </a>
</div>
```

---

## Checklist da Fase 4

- [ ] `pretty_midi` reativado em `requirements.pipeline.txt` (verificar compatibilidade)
- [ ] `music21` adicionado em `requirements.pipeline.txt`
- [ ] `app/use_cases/generate_drum_midi.py` criado
- [ ] Função `quantize_hits()` implementada e testada
- [ ] Arquivo `.mid` gerado corretamente (testado no MuseScore ou GarageBand)
- [ ] Arquivo `.musicxml` gerado corretamente (partitura legível)
- [ ] Endpoints `/midi` e `/musicxml` adicionados ao `main.py`
- [ ] Botões de download visíveis no workspace após análise concluída
- [ ] Notas de bumbo (36) e caixa (38) aparecem nas posições corretas na partitura

---

## Próxima Fase

A **Fase 5** usa os dados de BPM, beats e hits da análise para construir a timeline visual no frontend — a waveform do stem de bateria com marcadores coloridos em cada golpe detectado.

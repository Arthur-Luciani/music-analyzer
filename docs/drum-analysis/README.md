# 🥁 Drum Analysis — Plano de Implementação

**Data**: 29 de abril de 2026
**Status**: Planejado, aguardando execução
**Objetivo**: Evoluir o `music-analyzer` com análise profunda do stem de bateria

---

## O que este plano entrega

A partir do stem de **drums** isolado pelo Demucs, o plano adiciona quatro capacidades novas:

| Capacidade | Entregável para o usuário |
|---|---|
| BPM e beat tracking | Velocidade da música + posição de cada batida |
| Detecção e classificação de golpes | Cada golpe identificado: kick, snare, hi-hat, tom, prato |
| Partitura e MIDI | Download da transcrição em formato universal (.mid, .musicxml) |
| Timeline visual sincronizada | Waveform com marcadores coloridos + partitura que segue o playback |

---

## Por que começar pelo stem isolado?

O Demucs já entrega um arquivo de áudio com **somente a bateria**. Isso elimina o maior problema de análise rítmica — o ruído das outras faixas (vocais, baixo, guitarra). Todas as análises abaixo partem desse stem limpo, o que torna os resultados significativamente mais precisos.

---

## Fases de Execução

| Fase | Área | Descrição | Duração Est. | Depende de |
|---|---|---|---|---|
| 1 | Backend | BPM, Beat Tracking e API de análise | 3–4 dias | — |
| 2 | Backend | Onset Detection e Dataset de treinamento | 4–5 dias | Fase 1 |
| 3 | Backend | Treinamento do classificador de instrumentos | 3–5 dias | Fase 2 |
| 4 | Backend | Geração de MIDI e MusicXML | 3–4 dias | Fase 3 |
| 5 | Frontend | Timeline visual e waveform com marcadores | 4–6 dias | Fase 1 |
| 6 | Frontend | Partitura de bateria renderizada no browser | 4–5 dias | Fase 4 + 5 |

**Total estimado**: 21–29 dias de trabalho.

> Fases 1 e 5 podem ser iniciadas em paralelo. Fase 5 depende apenas dos dados de BPM/beats que a Fase 1 entrega.

---

## Dependências entre Fases

```
Fase 1 (BPM + Beats)
    ├── Fase 2 (Onset Detection + Dataset)
    │       └── Fase 3 (Treinamento do Classificador)
    │                   └── Fase 4 (MIDI + MusicXML)
    │                                   └── Fase 6 (Partitura no browser)
    └── Fase 5 (Timeline visual)
                └── Fase 6 (Partitura no browser)
```

---

## Stack Técnico

### Backend (dependências novas)

| Pacote | Já no projeto? | Para quê |
|---|---|---|
| `librosa>=0.10.2` | ✅ Instalado | BPM, beats, onsets, features espectrais |
| `torch / torchaudio` | ✅ Instalado | Treinamento e inferência do classificador |
| `numpy` | ✅ Instalado | Processamento dos arrays de áudio |
| `soundfile` | ✅ Instalado | Leitura dos stems de áudio |
| `pretty_midi>=0.2.10` | ⚠️ Listado, desabilitado | Geração do arquivo MIDI |
| `music21>=9.1` | ❌ Novo | Conversão MIDI → MusicXML |
| `mido>=1.3` | ❌ Novo | Escrita de MIDI de baixo nível (alternativa leve) |

### Frontend (dependências novas)

| Pacote | Para quê |
|---|---|
| `wavesurfer.js ^7` | Waveform do stem de drums + marcadores de beat/golpe |
| `vexflow ^4` | Renderização da partitura de bateria no browser |

---

## Novos Endpoints da API

| Método | Endpoint | Descrição | Fase |
|---|---|---|---|
| `POST` | `/api/sessions/{id}/drum-analysis` | Dispara análise do stem de drums | 1 |
| `GET` | `/api/sessions/{id}/drum-analysis` | Retorna resultado: BPM, beats, hits | 1 |
| `GET` | `/api/sessions/{id}/drum-analysis/midi` | Download do arquivo MIDI | 4 |
| `GET` | `/api/sessions/{id}/drum-analysis/musicxml` | Download do MusicXML | 4 |

---

## Novos Arquivos no Projeto

```
backend/app/
├── models/
│   └── drum_analysis.py          ← DrumHit, DrumAnalysis (Fase 1)
├── use_cases/
│   ├── analyze_drum_stem.py      ← AnalyzeDrumStemUseCase (Fase 1)
│   ├── classify_drum_hits.py     ← ClassifyDrumHitsUseCase (Fase 3)
│   └── generate_drum_midi.py     ← GenerateDrumMidiUseCase (Fase 4)
└── ml/
    ├── drum_classifier/
    │   ├── dataset.py            ← Carregamento do dataset (Fase 2)
    │   ├── model.py              ← Arquitetura da rede neural (Fase 3)
    │   ├── train.py              ← Script de treinamento (Fase 3)
    │   └── inference.py          ← Classificação em produção (Fase 3)
    └── data/
        └── drum_dataset/         ← Dataset de treinamento (Fase 2)

frontend/src/
├── hooks/
│   └── useDrumAnalysis.js        ← Hook de análise (Fase 5)
└── components/
    ├── DrumTimeline.jsx           ← Waveform + marcadores (Fase 5)
    └── DrumSheet.jsx              ← Partitura VexFlow (Fase 6)
```

---

## Documentos de Cada Fase

- [`PHASE_1_BPM_BEATS.md`](./PHASE_1_BPM_BEATS.md) — BPM, beat tracking, API de análise
- [`PHASE_2_ONSET_DATASET.md`](./PHASE_2_ONSET_DATASET.md) — Detecção de golpes e construção do dataset
- [`PHASE_3_CLASSIFIER.md`](./PHASE_3_CLASSIFIER.md) — Treinamento do classificador PyTorch
- [`PHASE_4_MIDI_SCORE.md`](./PHASE_4_MIDI_SCORE.md) — Geração de MIDI e MusicXML
- [`PHASE_5_TIMELINE.md`](./PHASE_5_TIMELINE.md) — Waveform e timeline sincronizada
- [`PHASE_6_SHEET.md`](./PHASE_6_SHEET.md) — Partitura de bateria no browser

---

## Princípios deste plano

- **Não quebrar o MVP**: cada fase é incremental e o app continua funcionando
- **Aproveitar o que já existe**: librosa, torch e GPU já instalados
- **Análise sob demanda**: a análise é disparada pelo usuário, não automaticamente no pipeline
- **Modelo próprio**: treinamos um classificador PyTorch nativo, sem dependências de TensorFlow ou madmom
- **Persistência**: resultado da análise é salvo em JSON junto à sessão, evitando reprocessamento

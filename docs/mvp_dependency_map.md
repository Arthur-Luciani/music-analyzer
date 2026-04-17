# Music Analyzer - Mapa de Dependencias do MVP

Este documento mapeia as bibliotecas externas sugeridas no plano do MVP, separando o que ja existe na base do que precisa ser ligado na implementacao de cada fase.

## Status atual da base

- Backend base pronto com FastAPI em backend/requirements.txt.
- Frontend base pronto com React + Vite em frontend/package.json.
- FFmpeg ja instalado no container backend em backend/Dockerfile.
- GPU habilitada no compose com gpus: all em docker-compose.yml.

## Fase 1 - Setup

| Dependencia | Tipo | Status | Onde |
|---|---|---|---|
| Docker Compose | Infra | Mapeada | docker-compose.yml |
| NVIDIA Container Toolkit | Infra host | Mapeada (host) | README.md |
| CUDA 11.8 | Runtime GPU | Mapeada | backend/requirements.pipeline.txt |
| FastAPI | Backend | Ativa | backend/requirements.txt |

## Fase 2 - Core

| Dependencia | Tipo | Status | Onde |
|---|---|---|---|
| Demucs (htdemucs) | Separacao de stems | Mapeada | backend/requirements.pipeline.txt |
| PyTorch + Torchaudio (cu118) | Execucao GPU | Mapeada | backend/requirements.pipeline.txt |
| yt-dlp | Download de audio | Mapeada | backend/requirements.pipeline.txt |
| Spotipy | Spotify API | Mapeada | backend/requirements.pipeline.txt |
| RapidFuzz | Match/ranking de resultados | Mapeada | backend/requirements.pipeline.txt |
| python-dotenv | Config por ambiente | Mapeada | backend/requirements.pipeline.txt |
| NumPy + SoundFile | IO/processamento audio | Mapeada | backend/requirements.pipeline.txt |

## Fase 3 - Player

| Dependencia | Tipo | Status | Onde |
|---|---|---|---|
| React | UI | Ativa | frontend/package.json |
| Vite | Build/dev | Ativa | frontend/package.json |
| WaveSurfer.js | Waveform | Mapeada | frontend/package.json |
| Web Audio API | Nativa do browser | Nao requer pacote | nativo |

## v2 - Analise (pos-MVP)

| Dependencia | Tipo | Status | Onde |
|---|---|---|---|
| Librosa | BPM/onset | Mapeada | backend/requirements.pipeline.txt |
| Basic Pitch | Notas e MIDI | Mapeada | backend/requirements.pipeline.txt |
| Pretty MIDI | Exportacao MIDI | Mapeada | backend/requirements.pipeline.txt |

## Como instalar por fase

Backend base:

```bash
pip install -r backend/requirements.txt
```

Backend pipeline (fase 2 e v2):

```bash
pip install -r backend/requirements.txt -r backend/requirements.pipeline.txt
```

Frontend (inclui WaveSurfer):

```bash
cd frontend
npm install
```

## Observacoes

- O arquivo backend/requirements.pipeline.txt foi separado para nao forcar instalacao pesada de GPU/ML quando a API base ainda estiver em modo mock.
- Em ambiente sem GPU, o pacote pode instalar, mas o processamento do Demucs pode ficar inviavel em tempo/praticidade.
- A validacao final de CUDA continua sendo torch.cuda.is_available() dentro do container backend.

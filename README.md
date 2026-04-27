# Music Analyzer MVP

Base do projeto com backend FastAPI, frontend React (Vite), Docker Compose e estrutura de storage para pipeline de separacao em stems com Demucs.

## Mapa de dependencias

- Mapeamento completo por fase (MVP + pos-MVP): docs/mvp_dependency_map.md
- Dependencias de pipeline (Demucs, yt-dlp, Spotipy, PyTorch cu118, analise v2): backend/requirements.pipeline.txt

## Estrutura

- `backend/`: API FastAPI com endpoint de processamento e WebSocket de progresso
- `frontend/`: UI React para disparar jobs e acompanhar status em tempo real
- `storage/raw/`: audio original
- `storage/stems/`: saida dos stems separados
- `storage/cache/`: cache de modelos
- `docker-compose.yml`: orquestracao dos servicos

## Subir o projeto com Docker

Prerequisitos:

1. Docker Desktop instalado
2. NVIDIA Container Toolkit instalado no host
3. Driver NVIDIA atualizado

Comandos:

```bash
docker compose build
docker compose up
```

## Variaveis de ambiente do pipeline

Backend (service `backend` no compose):

- `SEPARATION_MODEL` (default: `htdemucs`)
- `SEPARATION_DEVICE` (`auto`, `cuda`, `cpu`)
- `SEPARATION_SEGMENT` (default: `7`)
- `SEPARATION_OVERLAP` (default: `0.25`)
- `SEPARATION_SHIFTS` (default: `1`)
- `SEPARATION_TARGET_STEMS` (default: `vocals,drums,bass,other`)
- `TORCH_HOME` (default no compose: `/app/storage/cache/torch`)

Com `SEPARATION_DEVICE=auto`, o backend tenta `cuda` primeiro e faz fallback para `cpu` quando necessario.

Instalacao local por fase (sem Docker):

```bash
pip install -r backend/requirements.txt
pip install -r backend/requirements.txt -r backend/requirements.pipeline.txt
cd frontend && npm install
```

Para separacao local (fora do Docker), tenha FFmpeg instalado e disponivel no PATH do sistema.
Se necessario, defina `FFMPEG_BINARY` com o caminho completo de `ffmpeg.exe`.

### Rodar local (Windows)

Use o script da raiz para iniciar backend/frontend com variaveis corretas para storage e GPU:

```powershell
.\run-local-dev.ps1 -Target all -SeparationDevice cuda
```

Somente backend:

```powershell
.\run-local-dev.ps1 -Target backend -SeparationDevice cuda
```

Somente frontend:

```powershell
.\run-local-dev.ps1 -Target frontend
```

Verificar status dos servicos:

```powershell
.\run-local-dev.ps1 -Target check
```

Se FFmpeg nao estiver instalado:

```powershell
winget install --id Gyan.FFmpeg --source winget
```

Servicos:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Healthcheck backend: http://localhost:8000/health

## API MVP

- `POST /api/process`
  - body: `{ "query": "artist + song", "target_stems": ["vocals", "drums"] }`
  - resposta: `{ "job_id": "..." }`
- `GET /api/jobs/{job_id}`
- `WS /ws/{job_id}`

## Teste rapido de fluxo

1. Abrir o frontend em http://localhost:5173
2. Enviar uma busca (ex: `Daft Punk Get Lucky`)
3. Ver progresso em tempo real: `queued -> downloading -> separating -> ready`
4. Conferir arquivos reais em `storage/stems/{job_id}/vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`

## Sobre GPU

A base do backend ja esta com `gpus: all` no Docker Compose.

Para validar CUDA no seu ambiente, execute dentro do container backend:

```bash
docker compose exec backend python -c "import torch; print(torch.cuda.is_available())"
```

Em execucao real, o pipeline usa Demucs para gerar os 4 stems. Em maquinas sem GPU, use `SEPARATION_DEVICE=cpu`.

Validacao rapida de CUDA local (fora do Docker):

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

### Troubleshooting CUDA

Se ocorrer erro de memoria na GPU:

1. Force CPU temporariamente com `SEPARATION_DEVICE=cpu`.
2. Reduza carga com `SEPARATION_SHIFTS=1` (ou mantenha nesse valor).
3. Ajuste `SEPARATION_SEGMENT` para um valor menor se necessario.

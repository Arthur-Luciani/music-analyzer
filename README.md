# Music Analyzer MVP

Base inicial do projeto com backend FastAPI, frontend React (Vite), Docker Compose e estrutura de storage para pipeline de separacao em stems.

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

Instalacao local por fase (sem Docker):

```bash
pip install -r backend/requirements.txt
pip install -r backend/requirements.txt -r backend/requirements.pipeline.txt
cd frontend && npm install
```

Servicos:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Healthcheck backend: http://localhost:8000/health

## API MVP

- `POST /api/process`
  - body: `{ "query": "artist + song" }`
  - resposta: `{ "job_id": "..." }`
- `GET /api/jobs/{job_id}`
- `WS /ws/{job_id}`

## Teste rapido de fluxo

1. Abrir o frontend em http://localhost:5173
2. Enviar uma busca (ex: `Daft Punk Get Lucky`)
3. Ver progresso em tempo real: `queued -> downloading -> separating -> ready`

## Sobre GPU

A base do backend ja esta com `gpus: all` no Docker Compose.

Para validar CUDA no seu ambiente, execute dentro do container backend:

```bash
docker compose exec backend python -c "import torch; print(torch.cuda.is_available())"
```

No estado atual, o pipeline de processamento esta mockado (simulado) para validar arquitetura REST + WebSocket. As integracoes reais com yt-dlp, Demucs e Spotipy entram na proxima etapa.

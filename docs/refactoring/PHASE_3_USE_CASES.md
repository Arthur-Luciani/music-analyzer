# Fase 3: Refatoração de JobService em Casos de Uso

**Duração**: 2-3 dias  
**Objetivo**: Extrair lógica de negócio de `JobService` em casos de uso menores e testáveis  
**Saída**: Serviço simplificado, casos de uso isolados, endpoints inalterados

---

## Contexto

Hoje `JobService` concentra: busca, criação de sessão, duplicação, reprocessamento, pipeline de processamento, gerenciamento de mix-state, exportação. O objetivo é separar cada "fluxo de negócio" em um caso de uso isolado.

### Benefício
- Cada caso de uso fica testável isoladamente
- Lógica fica mais legível
- Reutilização de casos de uso em diferentes contextos (CLI, WebSocket, scheduler)
- JobService vira orquestrador, não executor

---

## Estrutura Alvo

```
backend/app/use_cases/
├── __init__.py
├── search_candidates.py         # SearchCandidatesUseCase
├── create_session.py            # CreateSessionUseCase
├── process_session.py           # ProcessSessionUseCase (pipeline)
├── duplicate_session.py         # DuplicateSessionUseCase
├── reprocess_session.py         # ReprocessSessionUseCase
├── manage_mix_state.py          # GetMixStateUseCase, SaveMixStateUseCase
├── manage_export.py             # CreateExportUseCase, RunExportUseCase
└── list_sessions.py             # ListSessionsUseCase
```

---

## Etapas

### 3.1 SearchCandidatesUseCase

**Arquivo**: `backend/app/use_cases/search_candidates.py`

```python
from dataclasses import dataclass
from typing import Optional
from app.models import SearchResponse
from app.services.jobs import JobService  # Reutiliza lógica de busca

@dataclass
class SearchCandidatesUseCase:
    """Busca candidatos de música para processar."""
    
    _job_service: JobService
    
    def execute(self, query: str, limit: int = 5) -> SearchResponse:
        """Busca candidatos usando a lógica existente."""
        return self._job_service.search_candidates(query, limit=limit)
```

### 3.2 CreateSessionUseCase

**Arquivo**: `backend/app/use_cases/create_session.py`

```python
from dataclasses import dataclass
from typing import Optional
from app.models import SearchCandidate, JobStatus
from app.services.jobs import JobService

@dataclass
class CreateSessionUseCase:
    """Cria nova sessão a partir de busca."""
    
    _job_service: JobService
    
    async def execute(
        self,
        query: str,
        selected_track: Optional[SearchCandidate] = None,
        target_stems: Optional[list[str]] = None,
    ) -> JobStatus:
        """Cria sessão e retorna status inicial."""
        return await self._job_service.create_job(
            query,
            selected_track=selected_track,
            target_stems=target_stems,
        )
```

### 3.3 ProcessSessionUseCase

**Arquivo**: `backend/app/use_cases/process_session.py`

```python
from dataclasses import dataclass
from app.services.jobs import JobService

@dataclass
class ProcessSessionUseCase:
    """Executa pipeline de processamento (download + separação)."""
    
    _job_service: JobService
    
    async def execute(self, job_id: str) -> None:
        """Processa sessão até ficar pronta ou falhar."""
        await self._job_service.run_pipeline(job_id)
```

### 3.4 Outros Casos de Uso (Similar)

Cada um segue o mesmo padrão: uma classe com `_job_service` injetado e método `execute()`.

---

### 3.5 Refatorar JobService para Orquestrador

**No `JobService`**:

```python
class JobService:
    def __init__(self):
        self._jobs: Dict[str, JobStatus] = {}
        self._subscribers: Dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._recent_searches: Dict[str, list[SearchCandidate]] = {}
        self._store = SessionRepository(settings.sessions_db_path)
        
        # Injetar casos de uso
        self._search_use_case = SearchCandidatesUseCase(self)
        self._create_session_use_case = CreateSessionUseCase(self)
        self._process_session_use_case = ProcessSessionUseCase(self)
        # ... etc
```

Os métodos existentes delegam para os casos de uso:

```python
def search_candidates(self, query: str, limit: int = 5) -> SearchResponse:
    return self._search_use_case.execute(query, limit)

async def create_job(self, query: str, ...) -> JobStatus:
    return await self._create_session_use_case.execute(query, ...)
```

---

## Checklist de Conclusão da Fase 3

- [ ] Arquivo `backend/app/use_cases/__init__.py` criado
- [ ] 8 casos de uso criados (search, create, process, duplicate, reprocess, mix_get, mix_save, export)
- [ ] Cada caso de uso tem método `execute()` testável
- [ ] JobService delegaa para casos de uso, não executa lógica diretamente
- [ ] Endpoints continuam funcionando (API inalterada)
- [ ] Smoke test de pipeline passa
- [ ] Backend compila: `python -m compileall app`

---

## Próximas Fases

Fase 4 vai fazer refatoração similar no frontend, extraindo a lógica de `App.jsx` em hooks reutilizáveis.

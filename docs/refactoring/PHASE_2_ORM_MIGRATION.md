# Fase 2: Migração de Tabelas para ORM

**Duração**: 3-4 dias  
**Objetivo**: Reimplementar `SessionRepository` usando ORM, mantendo interface compatível com JobService  
**Saída**: Repositório baseado em ORM, endpoints funcionando, sem regressão

---

## Contexto

Fase 1 criou os modelos ORM. Agora precisamos reimplementar o `SQLiteSessionStore` (ou criar um novo `SessionRepository` usando ORM) de forma que a interface pública permaneça idêntica. Isso permite migração gradual sem quebrar nada.

### Abordagem

1. Criar `backend/app/repositories/session_repository.py` usando ORM
2. Manter o mesmo contrato de métodos públicos
3. Validar cada método com testes antes de trocar de implementação
4. Apenas depois de validado, trocar o import em `JobService`

---

## Estrutura Alvo

```
backend/app/repositories/
├── __init__.py
├── session_store.py       # Implementação legada (mantém durante fase 2)
├── session_repository.py  # Implementação nova com ORM
└── ...
```

---

## Etapa por Etapa

### 2.1 Criar Session Repository com ORM

**Arquivo**: `backend/app/repositories/session_repository.py`

```python
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.db.config import SessionLocal
from app.db.models import (
    SessionORM, SessionMixStateORM, ExportJobORM, SessionEventORM
)
from app.models import (
    ExportArtifact, ExportJob, ExportState, JobState, JobStatus,
    MasterMetrics, MixState, SearchCandidate, SessionEvent
)
from app.settings import settings


class SessionRepository:
    """Repositório baseado em ORM para gerenciar sessões."""
    
    def __init__(self, db_session: Optional[Session] = None):
        self._session = db_session or SessionLocal()
    
    @staticmethod
    def _serialize_candidate(candidate: Optional[SearchCandidate]) -> Optional[str]:
        import json
        if candidate is None:
            return None
        return json.dumps(candidate.model_dump(mode="json"), ensure_ascii=True)
    
    @staticmethod
    def _deserialize_candidate(raw: Optional[str]) -> Optional[SearchCandidate]:
        import json
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return SearchCandidate.model_validate(payload)
        except Exception:
            return None
    
    @staticmethod
    def _to_json_payload(value: object) -> str:
        import json
        return json.dumps(value, ensure_ascii=True)
    
    @staticmethod
    def _parse_datetime(raw: str) -> datetime:
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return datetime.utcnow()
    
    @staticmethod
    def _safe_state(raw: str) -> JobState:
        try:
            return JobState(raw)
        except Exception:
            return JobState.failed
    
    @staticmethod
    def _safe_export_state(raw: str) -> ExportState:
        try:
            return ExportState(raw)
        except Exception:
            return ExportState.failed
    
    def _next_session_code(self) -> str:
        """Gera próximo código de sessão (MX-001, MX-002, etc)."""
        from sqlalchemy import func, text
        # Usa raw SQL para simplificar a operação de contador
        result = self._session.query(func.max(
            func.cast(
                func.substr(SessionORM.session_code, 4),
                self._session.bind.dialect.type_descriptor(type(1))
            )
        )).scalar()
        sequence = (result or 0) + 1
        return f"MX-{sequence:03d}"
    
    def create_session(
        self,
        *,
        session_id: str,
        query: str,
        selected_track: Optional[SearchCandidate],
        target_stems: list[str],
        state: JobState,
        progress: int,
        message: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> str:
        """Cria nova sessão no banco, retorna session_code."""
        import json
        
        session_code = self._next_session_code()
        
        orm_session = SessionORM(
            id=session_id,
            session_code=session_code,
            query=query,
            selected_track_json=self._serialize_candidate(selected_track),
            track_title=selected_track.title if selected_track else None,
            artist=selected_track.artist if selected_track else None,
            target_stems_json=self._to_json_payload(target_stems),
            state=state.value,
            progress=progress,
            message=message,
            created_at=created_at,
            updated_at=updated_at,
        )
        
        self._session.add(orm_session)
        self._session.commit()
        
        return session_code
    
    def save_session(self, job: JobStatus) -> None:
        """Atualiza sessão existente."""
        import json
        
        orm_session = self._session.query(SessionORM).filter(
            SessionORM.id == job.session_id
        ).first()
        
        if not orm_session:
            raise ValueError(f"Session {job.session_id} not found")
        
        orm_session.query = job.query
        orm_session.selected_track_json = self._serialize_candidate(job.selected_track)
        orm_session.track_title = job.selected_track.title if job.selected_track else None
        orm_session.artist = job.selected_track.artist if job.selected_track else None
        orm_session.target_stems_json = self._to_json_payload(job.target_stems)
        orm_session.state = job.state.value
        orm_session.progress = job.progress
        orm_session.message = job.message
        orm_session.stems_json = self._to_json_payload(job.stems) if job.stems else None
        orm_session.error = job.error
        orm_session.eta_seconds = job.estimated_remaining_seconds
        orm_session.separation_device = job.separation_device
        orm_session.master_metrics_json = (
            self._to_json_payload(job.master_metrics.model_dump(mode="json"))
            if job.master_metrics else None
        )
        orm_session.updated_at = job.updated_at
        
        self._session.commit()
    
    def get_session(self, session_id: str) -> Optional[JobStatus]:
        """Lê sessão pelo ID."""
        orm_session = self._session.query(SessionORM).filter(
            SessionORM.id == session_id
        ).first()
        
        if not orm_session:
            return None
        
        return self._orm_to_job_status(orm_session)
    
    def list_sessions(
        self,
        *,
        query: Optional[str],
        status: Optional[JobState],
        created_from: Optional[datetime],
        created_to: Optional[datetime],
        page: int,
        page_size: int,
    ) -> tuple[list[JobStatus], int]:
        """Lista sessões com filtros, retorna (items, total)."""
        q = self._session.query(SessionORM)
        
        if query:
            query_like = f"%{query.strip()}%"
            from sqlalchemy import or_
            q = q.filter(or_(
                SessionORM.query.ilike(query_like),
                SessionORM.track_title.ilike(query_like),
                SessionORM.artist.ilike(query_like),
                SessionORM.session_code.ilike(query_like),
            ))
        
        if status is not None:
            q = q.filter(SessionORM.state == status.value)
        
        if created_from is not None:
            q = q.filter(SessionORM.created_at >= created_from)
        
        if created_to is not None:
            q = q.filter(SessionORM.created_at <= created_to)
        
        total = q.count()
        
        offset = max(0, (page - 1) * page_size)
        limit = max(1, page_size)
        
        rows = q.order_by(desc(SessionORM.created_at)).offset(offset).limit(limit).all()
        
        jobs = [self._orm_to_job_status(row) for row in rows]
        return jobs, total
    
    def get_mix_state_payload(self, session_id: str) -> Optional[dict[str, object]]:
        """Lê mix-state de uma sessão."""
        import json
        
        orm_mix = self._session.query(SessionMixStateORM).filter(
            SessionMixStateORM.session_id == session_id
        ).first()
        
        if not orm_mix:
            return None
        
        try:
            payload = json.loads(orm_mix.payload_json)
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        
        payload["updated_at"] = orm_mix.updated_at.isoformat()
        return payload
    
    def save_mix_state_payload(self, session_id: str, payload: dict[str, object], updated_at: datetime) -> None:
        """Salva ou atualiza mix-state de uma sessão."""
        import json
        
        orm_mix = self._session.query(SessionMixStateORM).filter(
            SessionMixStateORM.session_id == session_id
        ).first()
        
        payload_json = self._to_json_payload(payload)
        
        if orm_mix:
            orm_mix.payload_json = payload_json
            orm_mix.updated_at = updated_at
        else:
            orm_mix = SessionMixStateORM(
                session_id=session_id,
                payload_json=payload_json,
                updated_at=updated_at,
            )
            self._session.add(orm_mix)
        
        self._session.commit()
    
    def create_export_job(
        self,
        *,
        export_id: str,
        session_id: str,
        preset: str,
        format_name: str,
        state: ExportState,
        progress: int,
        created_at: datetime,
        updated_at: datetime,
    ) -> ExportJob:
        """Cria novo job de exportação."""
        orm_export = ExportJobORM(
            id=export_id,
            session_id=session_id,
            preset=preset,
            format=format_name,
            state=state.value,
            progress=progress,
            output_json="[]",
            error=None,
            created_at=created_at,
            updated_at=updated_at,
        )
        
        self._session.add(orm_export)
        self._session.commit()
        
        return ExportJob(
            export_id=export_id,
            session_id=session_id,
            preset=preset,
            format=format_name,
            state=state,
            progress=progress,
            output_files=[],
            error=None,
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def save_export_job(self, export_job: ExportJob) -> None:
        """Atualiza job de exportação."""
        orm_export = self._session.query(ExportJobORM).filter(
            ExportJobORM.id == export_job.export_id
        ).first()
        
        if not orm_export:
            raise ValueError(f"Export {export_job.export_id} not found")
        
        orm_export.preset = export_job.preset
        orm_export.format = export_job.format
        orm_export.state = export_job.state.value
        orm_export.progress = export_job.progress
        orm_export.output_json = self._to_json_payload(
            [f.model_dump(mode="json") for f in export_job.output_files]
        )
        orm_export.error = export_job.error
        orm_export.updated_at = export_job.updated_at
        
        self._session.commit()
    
    def get_export_job(self, session_id: str, export_id: str) -> Optional[ExportJob]:
        """Lê job de exportação."""
        orm_export = self._session.query(ExportJobORM).filter(
            and_(
                ExportJobORM.session_id == session_id,
                ExportJobORM.id == export_id,
            )
        ).first()
        
        if not orm_export:
            return None
        
        return self._orm_to_export_job(orm_export)
    
    def list_export_jobs(self, session_id: str) -> list[ExportJob]:
        """Lista jobs de exportação de uma sessão."""
        rows = self._session.query(ExportJobORM).filter(
            ExportJobORM.session_id == session_id
        ).order_by(desc(ExportJobORM.created_at)).all()
        
        return [self._orm_to_export_job(row) for row in rows]
    
    def append_session_event(
        self,
        *,
        session_id: str,
        timestamp: datetime,
        stage: str,
        level: str,
        progress: int,
        message: str,
    ) -> None:
        """Adiciona evento de sessão."""
        orm_event = SessionEventORM(
            session_id=session_id,
            ts=timestamp,
            stage=stage,
            level=level,
            progress=progress,
            message=message,
        )
        
        self._session.add(orm_event)
        self._session.commit()
    
    def list_session_events(self, session_id: str) -> list[SessionEvent]:
        """Lista eventos de uma sessão."""
        rows = self._session.query(SessionEventORM).filter(
            SessionEventORM.session_id == session_id
        ).order_by(SessionEventORM.ts.asc()).all()
        
        events = []
        for row in rows:
            events.append(
                SessionEvent(
                    timestamp=row.ts,
                    stage=row.stage,
                    level=row.level,
                    progress=max(0, min(100, row.progress)),
                    message=row.message,
                )
            )
        
        return events
    
    # Helpers privados
    
    def _orm_to_job_status(self, orm_session: SessionORM) -> JobStatus:
        """Converte ORM SessionORM para modelo JobStatus."""
        import json
        
        target_stems = list(settings.separation_target_stems)
        if orm_session.target_stems_json:
            try:
                payload = json.loads(orm_session.target_stems_json)
                if isinstance(payload, list):
                    parsed = [str(item).strip().lower() for item in payload if str(item).strip()]
                    if parsed:
                        target_stems = parsed
            except Exception:
                pass
        
        stems_payload: Optional[Dict[str, str]] = None
        if orm_session.stems_json:
            try:
                parsed_stems = json.loads(orm_session.stems_json)
                if isinstance(parsed_stems, dict):
                    stems_payload = {str(key): str(value) for key, value in parsed_stems.items()}
            except Exception:
                stems_payload = None
        
        eta_seconds = None
        if orm_session.eta_seconds is not None:
            try:
                eta_seconds = max(0, int(orm_session.eta_seconds))
            except Exception:
                eta_seconds = None
        
        separation_device = None
        if isinstance(orm_session.separation_device, str):
            separation_device = orm_session.separation_device.strip().lower() or None
        
        master_metrics: Optional[MasterMetrics] = None
        if orm_session.master_metrics_json:
            try:
                import json
                payload = json.loads(orm_session.master_metrics_json)
                master_metrics = MasterMetrics.model_validate(payload)
            except Exception:
                master_metrics = None
        
        return JobStatus(
            job_id=orm_session.id,
            session_id=orm_session.id,
            session_code=orm_session.session_code,
            query=orm_session.query,
            selected_track=self._deserialize_candidate(orm_session.selected_track_json),
            target_stems=target_stems,
            state=self._safe_state(orm_session.state),
            progress=max(0, min(100, orm_session.progress)),
            message=orm_session.message,
            created_at=orm_session.created_at,
            updated_at=orm_session.updated_at,
            stems=stems_payload,
            error=orm_session.error,
            estimated_remaining_seconds=eta_seconds,
            separation_device=separation_device,
            master_metrics=master_metrics,
        )
    
    def _orm_to_export_job(self, orm_export: ExportJobORM) -> ExportJob:
        """Converte ORM ExportJobORM para modelo ExportJob."""
        import json
        
        output_files: list[ExportArtifact] = []
        if orm_export.output_json:
            try:
                payload = json.loads(orm_export.output_json)
                if isinstance(payload, list):
                    output_files = [ExportArtifact.model_validate(item) for item in payload]
            except Exception:
                output_files = []
        
        return ExportJob(
            export_id=orm_export.id,
            session_id=orm_export.session_id,
            preset=orm_export.preset,
            format=orm_export.format,
            state=self._safe_export_state(orm_export.state),
            progress=max(0, min(100, orm_export.progress)),
            output_files=output_files,
            error=orm_export.error,
            created_at=orm_export.created_at,
            updated_at=orm_export.updated_at,
        )
```

**Validação**:
```bash
cd backend
python -c "from app.repositories.session_repository import SessionRepository; print('OK')"
```

---

### 2.2 Testes de Repositório

**Arquivo**: `backend/tests/test_session_repository.py`

```python
import pytest
from datetime import datetime
from app.repositories.session_repository import SessionRepository
from app.models import SearchCandidate, JobState, ExportState
from app.db.config import SessionLocal

@pytest.fixture
def repo():
    session = SessionLocal()
    repo = SessionRepository(db_session=session)
    yield repo
    session.close()

def test_create_and_get_session(repo):
    """Testa criação e leitura de sessão."""
    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )
    
    code = repo.create_session(
        session_id="test-1",
        query="test query",
        selected_track=cand,
        target_stems=["vocals", "drums"],
        state=JobState.queued,
        progress=0,
        message="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    assert code.startswith("MX-")
    
    loaded = repo.get_session("test-1")
    assert loaded is not None
    assert loaded.session_code == code
    assert loaded.query == "test query"

def test_list_sessions_with_filter(repo):
    """Testa listagem com filtro."""
    # Cria 3 sessões
    for i in range(3):
        cand = SearchCandidate(
            source_id=f"yt_{i}",
            source="youtube",
            title=f"Song {i}",
            artist=f"Artist {i}",
            duration_seconds=100,
            url=f"https://example.com/{i}",
        )
        repo.create_session(
            session_id=f"test-{i}",
            query=f"query {i}",
            selected_track=cand,
            target_stems=["vocals"],
            state=JobState.queued if i < 2 else JobState.ready,
            progress=0 if i < 2 else 100,
            message="test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    
    # Lista com filtro de status
    items, total = repo.list_sessions(
        query=None,
        status=JobState.ready,
        created_from=None,
        created_to=None,
        page=1,
        page_size=10,
    )
    
    assert total == 1
    assert len(items) == 1

def test_mix_state_persistence(repo):
    """Testa persistência de mix-state."""
    cand = SearchCandidate(
        source_id="yt_test",
        source="youtube",
        title="Test",
        artist="Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )
    
    code = repo.create_session(
        session_id="test-mix",
        query="test",
        selected_track=cand,
        target_stems=["vocals"],
        state=JobState.queued,
        progress=0,
        message="test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    payload = {"per_stem": {"vocals": {"gain": 3.0}}, "master_gain": -1.5}
    repo.save_mix_state_payload("test-mix", payload, datetime.utcnow())
    
    loaded = repo.get_mix_state_payload("test-mix")
    assert loaded is not None
    assert float(loaded["master_gain"]) == -1.5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Rodando testes**:
```bash
cd backend
pip install pytest
pytest tests/test_session_repository.py -v
```

---

### 2.3 Validar Compatibilidade

Antes de trocar no `JobService`, criar um script de validação que testa ambas as implementações:

**Arquivo**: `backend/tests/test_migration_compat.py`

```python
"""Valida que a nova implementação ORM é compatível com a legada."""
import asyncio
from app.repositories.session_store import SQLiteSessionStore
from app.repositories.session_repository import SessionRepository
from app.models import SearchCandidate, JobState
from datetime import datetime

async def test_both_implementations():
    """Testa operações em ambas as implementações."""
    from app.settings import settings
    
    # Instancia ambas
    store_legacy = SQLiteSessionStore(settings.sessions_db_path)
    store_orm = SessionRepository()
    
    cand = SearchCandidate(
        source_id="yt_compat",
        source="youtube",
        title="Compatibility Test",
        artist="Test Artist",
        duration_seconds=100,
        url="https://example.com/v",
    )
    
    # Cria em ORM
    code_orm = store_orm.create_session(
        session_id="compat-orm-1",
        query="compat test",
        selected_track=cand,
        target_stems=["vocals"],
        state=JobState.queued,
        progress=0,
        message="test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    print(f"ORM created: {code_orm}")
    
    # Lê em ORM
    loaded_orm = store_orm.get_session("compat-orm-1")
    print(f"ORM loaded: {loaded_orm.session_code if loaded_orm else 'none'}")
    
    # Lê a mesma sessão usando implementação legada
    loaded_legacy = store_legacy.get_session("compat-orm-1")
    print(f"Legacy loaded ORM data: {loaded_legacy.session_code if loaded_legacy else 'none'}")
    
    assert code_orm == (loaded_legacy.session_code if loaded_legacy else None)
    print("✓ Ambas implementações leem a mesma sessão corretamente")

if __name__ == "__main__":
    asyncio.run(test_both_implementations())
```

**Rodando**:
```bash
cd backend
python tests/test_migration_compat.py
```

---

### 2.4 Trocar em JobService (quando validado)

Uma vez que testes passem, editar `backend/app/services/jobs.py`:

```python
# Antes:
from app.repositories.session_store import SQLiteSessionStore
self._store = SQLiteSessionStore(settings.sessions_db_path)

# Depois:
from app.repositories.session_repository import SessionRepository
self._store = SessionRepository()
```

**Validação**: Smoke test original passa ainda
```bash
cd backend
$env:STORAGE_ROOT="../storage"
python -c "import asyncio; from app.services.jobs import JobService; from app.models import SearchCandidate; svc=JobService(); cand=SearchCandidate(source_id='yt_test', source='youtube', title='Test', artist='A', duration_seconds=100, url='https://ex.com/v'); job=asyncio.run(svc.create_job('smoke', selected_track=cand)); print('job=', job.session_code)"
```

---

## Checklist de Conclusão da Fase 2

- [ ] `backend/app/repositories/session_repository.py` criado com ORM
- [ ] Todos os 9 métodos públicos implementados (create_session, save_session, get_session, list_sessions, get/save_mix_state, create/save/get_export_job, list_export, append/list_event)
- [ ] Testes de repositório passam: `pytest tests/test_session_repository.py -v`
- [ ] Teste de compatibilidade passa: `python tests/test_migration_compat.py`
- [ ] Importação em JobService trocada (de SQLiteSessionStore para SessionRepository)
- [ ] Smoke test legado de criar/listar/ler sessão passa
- [ ] Backend compila: `python -m compileall app`
- [ ] Nenhum endpoint quebrado (validar com `curl` ou Postman)

---

## Próximas Fases

Fase 3 vai refatorar `JobService` em casos de uso menores e mais testáveis, mantendo a interface dos endpoints igual. A persistência agora está em ORM e pronta para evoluir.

---

## Recursos Úteis

- SQLAlchemy Query API: https://docs.sqlalchemy.org/en/20/orm/query.html
- Testing with SQLAlchemy: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-the-session-with-events
- Pytest Fixtures: https://docs.pytest.org/en/latest/how-to/fixtures.html

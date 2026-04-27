# Fase 5: Implementar Test Coverage

**Duração**: 3-4 dias  
**Objetivo**: Implementar testes para código novo (use cases, repositórios, hooks)  
**Saída**: >70% cobertura de linhas de novo código; testes integração passando

---

## Contexto

Após Fases 1-4:
- Backend reorganizado em camadas (main.py → use cases → repositories → models)
- ORM em place (SQLAlchemy 2.x + Alembic)
- Frontend com hooks isolados e containers
- Nenhuma nova funcionalidade; apenas reorganização

Teste aqui serve para validar que refatoração não quebrou nada.

---

## 5.1 Setup de Testes Backend

### Dependências

```bash
pip install pytest pytest-asyncio pytest-cov httpx sqlalchemy
```

### Estrutura

```
backend/
├── tests/
│   ├── conftest.py               # Fixtures compartilhadas
│   ├── test_models.py            # Pydantic models
│   ├── repositories/
│   │   ├── test_session_store.py # SQLiteSessionStore (Phase 0)
│   │   └── test_session_repository.py # ORM SessionRepository (Phase 2)
│   ├── application/
│   │   ├── test_search_use_case.py
│   │   ├── test_process_job_use_case.py
│   │   ├── test_export_use_case.py
│   │   ├── test_duplicate_session_use_case.py
│   │   └── test_mix_state_use_case.py
│   └── routes/
│       ├── test_process_route.py      # POST /api/process
│       ├── test_session_route.py      # GET /api/sessions/:id
│       └── test_export_route.py       # GET/POST /api/exports
├── app/
│   ├── repositories/
│   ├── application/
│   ├── main.py
│   └── ...
└── requirements.txt
```

---

## 5.2 Fixtures Compartilhadas

**Arquivo**: `backend/tests/conftest.py`

```python
import pytest
import tempfile
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models import Base  # SQLAlchemy declarative base
from app.repositories.session_store import SQLiteSessionStore
from app.repositories.session_repository import SessionRepository

@pytest.fixture
def temp_db_sqlite():
    """In-memory SQLite for synchronous tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Init schema (use actual schema from app)
    from app.repositories.session_store import SQLITE_SCHEMA
    for statement in SQLITE_SCHEMA.split(";"):
        if statement.strip():
            cursor.execute(statement)
    conn.commit()
    
    yield db_path
    
    conn.close()
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture
def session_store(temp_db_sqlite):
    """SQLiteSessionStore instance."""
    return SQLiteSessionStore(temp_db_sqlite)

@pytest.fixture
def test_db_engine():
    """SQLAlchemy test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def test_session(test_db_engine) -> Session:
    """SQLAlchemy session."""
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def session_repository(test_session):
    """ORM SessionRepository."""
    return SessionRepository(test_session)

@pytest.fixture
def test_client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

@pytest.fixture
def mock_settings(monkeypatch, temp_db_sqlite):
    """Mock settings with temp DB."""
    monkeypatch.setenv("SESSIONS_DB_PATH", temp_db_sqlite)
    monkeypatch.setenv("STORAGE_ROOT", tempfile.gettempdir())
    
    from app import settings
    yield settings
```

---

## 5.3 Testes do Repositório

**Arquivo**: `backend/tests/repositories/test_session_store.py`

```python
import pytest
from app.repositories.session_store import SQLiteSessionStore
from app.models import JobStatus, ExportState

@pytest.mark.asyncio
async def test_session_store_create_session(session_store: SQLiteSessionStore):
    """Create new session and verify session_code generation."""
    session_code = session_store.create_session()
    
    assert len(session_code) == 6
    assert session_code.isupper()
    
    # Verify persistence
    sessions = session_store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_code"] == session_code

@pytest.mark.asyncio
async def test_session_store_get_session(session_store: SQLiteSessionStore):
    """Get existing session by session_id."""
    code = session_store.create_session()
    session = session_store.get_session(code)
    
    assert session is not None
    assert session["session_code"] == code
    assert session["status"] in ["idle", "processing", "ready", "failed"]

@pytest.mark.asyncio
async def test_session_store_save_session(session_store: SQLiteSessionStore):
    """Update session with new state."""
    code = session_store.create_session()
    
    session_store.save_session(
        code,
        {"status": "processing", "current_stage": "download"}
    )
    
    updated = session_store.get_session(code)
    assert updated["status"] == "processing"
    assert updated["current_stage"] == "download"

@pytest.mark.asyncio
async def test_session_store_list_with_filter(session_store: SQLiteSessionStore):
    """List sessions with status filter."""
    code1 = session_store.create_session()
    code2 = session_store.create_session()
    
    session_store.save_session(code1, {"status": "ready"})
    session_store.save_session(code2, {"status": "failed"})
    
    ready_sessions = session_store.list_sessions(status_filter="ready")
    assert len(ready_sessions) == 1
    assert ready_sessions[0]["session_code"] == code1

@pytest.mark.asyncio
async def test_session_store_mix_state_save_load(session_store: SQLiteSessionStore):
    """Save and load mix-state."""
    code = session_store.create_session()
    mix_state = {
        "per_stem": {
            "vocals": {"gain": 84},
            "drums": {"gain": 72}
        },
        "master_gain": 78
    }
    
    session_store.save_mix_state_payload(code, mix_state)
    
    loaded = session_store.get_mix_state_payload(code)
    assert loaded["per_stem"]["vocals"]["gain"] == 84
    assert loaded["master_gain"] == 78

@pytest.mark.asyncio
async def test_session_store_export_job_crud(session_store: SQLiteSessionStore):
    """Create, read, update export job."""
    code = session_store.create_session()
    
    job_id = session_store.create_export_job(
        code,
        preset="mixed_preview",
        format="wav",
        status="processing"
    )
    
    assert job_id is not None
    
    job = session_store.get_export_job(job_id)
    assert job["preset"] == "mixed_preview"
    
    session_store.update_export_job(job_id, {"status": "ready", "file_path": "/tmp/export.wav"})
    
    updated = session_store.get_export_job(job_id)
    assert updated["status"] == "ready"
    assert updated["file_path"] == "/tmp/export.wav"

@pytest.mark.asyncio
async def test_session_store_list_events(session_store: SQLiteSessionStore):
    """List session events."""
    code = session_store.create_session()
    
    session_store.save_session(code, {"status": "processing"})
    session_store.save_session(code, {"current_stage": "download"})
    
    events = session_store.list_session_events(code)
    assert len(events) >= 2
```

---

## 5.4 Testes de Use Cases

**Arquivo**: `backend/tests/application/test_search_use_case.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.application.search_use_case import SearchTracksUseCase

@pytest.mark.asyncio
async def test_search_tracks_use_case_success():
    """Search YouTube tracks and return candidates."""
    
    # Mock yt_dlp
    with patch('yt_dlp.YoutubeDL') as mock_ydl:
        mock_ydl.return_value.extract_info.return_value = {
            "entries": [
                {
                    "id": "abc123",
                    "title": "Song 1",
                    "duration": 180,
                    "uploader": "Artist"
                }
            ]
        }
        
        use_case = SearchTracksUseCase()
        result = await use_case.execute(query="rock music")
        
        assert len(result["candidates"]) >= 1
        assert result["candidates"][0]["title"] == "Song 1"

@pytest.mark.asyncio
async def test_search_tracks_use_case_empty_query():
    """Query too short should fail."""
    use_case = SearchTracksUseCase()
    
    with pytest.raises(ValueError, match="at least 3 characters"):
        await use_case.execute(query="ab")

@pytest.mark.asyncio
async def test_search_tracks_use_case_compatibility_scoring():
    """Calculate compatibility score based on duration."""
    with patch('yt_dlp.YoutubeDL'):
        use_case = SearchTracksUseCase()
        
        score = use_case._calculate_compatibility(180)  # 3 minutes
        assert 0 <= score <= 100
        
        score_long = use_case._calculate_compatibility(600)  # 10 minutes
        assert score_long < score  # Longer = less compatible
```

**Arquivo**: `backend/tests/application/test_process_job_use_case.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.process_job_use_case import ProcessJobUseCase
from app.repositories.session_repository import SessionRepository

@pytest.mark.asyncio
async def test_process_job_use_case_creates_job(session_repository):
    """ProcessJobUseCase creates job and starts pipeline."""
    use_case = ProcessJobUseCase(session_repository)
    
    # Create session first
    session_code = session_repository.create_session()
    
    result = await use_case.execute(
        session_code=session_code,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        source_id="abc123"
    )
    
    assert result["job_id"] is not None
    assert result["status"] == "processing"
    
    # Verify job persisted
    job = session_repository.get_job(result["job_id"])
    assert job is not None

@pytest.mark.asyncio
async def test_process_job_use_case_invalid_session(session_repository):
    """Invalid session should raise error."""
    use_case = ProcessJobUseCase(session_repository)
    
    with pytest.raises(ValueError, match="Session not found"):
        await use_case.execute(
            session_code="INVALID",
            youtube_url="https://...",
            source_id="abc"
        )
```

---

## 5.5 Testes de Rotas HTTP

**Arquivo**: `backend/tests/routes/test_process_route.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.asyncio
def test_post_api_process_success(test_client: TestClient, session_store):
    """POST /api/process creates job and returns job_id."""
    
    # Create session first
    session_code = session_store.create_session()
    
    response = test_client.post(
        "/api/process",
        json={
            "session_code": session_code,
            "source_id": "abc123",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["processing", "ready"]

def test_post_api_process_invalid_session(test_client: TestClient):
    """Invalid session code should return 400."""
    response = test_client.post(
        "/api/process",
        json={
            "session_code": "INVALID",
            "source_id": "abc123",
            "youtube_url": "https://..."
        }
    )
    
    assert response.status_code in [400, 422]

def test_get_api_session_success(test_client: TestClient, session_store):
    """GET /api/sessions/{session_id} returns session."""
    code = session_store.create_session()
    
    response = test_client.get(f"/api/sessions/{code}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_code"] == code
    assert "session_id" in data
```

---

## 5.6 Setup de Testes Frontend

### Dependências

```bash
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event msw
```

### Arquivo: `frontend/vitest.config.js`

```javascript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["src/**/*.{js,jsx}"],
      exclude: ["src/test/**", "**/*.test.{js,jsx}"],
    },
  },
});
```

### Arquivo: `frontend/src/test/setup.js`

```javascript
import "@testing-library/jest-dom";
import { expect, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

---

## 5.7 Testes de Hooks

**Arquivo**: `frontend/src/hooks/useDiscovery.test.jsx`

```javascript
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import { useDiscovery } from "./useDiscovery";

describe("useDiscovery", () => {
  it("should initialize with empty search state", () => {
    const { result } = renderHook(() => useDiscovery());
    
    expect(result.current.query).toBe("");
    expect(result.current.candidates).toEqual([]);
    expect(result.current.error).toBe("");
  });

  it("should update query on setQuery", () => {
    const { result } = renderHook(() => useDiscovery());
    
    act(() => {
      result.current.setQuery("test search");
    });
    
    expect(result.current.query).toBe("test search");
  });

  it("should show error if query < 3 chars", async () => {
    const { result } = renderHook(() => useDiscovery());
    
    act(() => {
      result.current.setQuery("ab");
    });
    
    await act(async () => {
      await result.current.runSearch("ab");
    });
    
    expect(result.current.error).toContain("at least 3");
  });

  it("should fetch candidates on valid search", async () => {
    const { result } = renderHook(() => useDiscovery());
    
    // Mock fetch
    global.fetch = async () => ({
      ok: true,
      json: async () => ({
        candidates: [
          { source_id: "123", title: "Song 1", duration: 180 }
        ],
        recommended_source_id: "123"
      })
    });
    
    await act(async () => {
      await result.current.runSearch("rock music");
    });
    
    await waitFor(() => {
      expect(result.current.candidates.length).toBe(1);
      expect(result.current.candidates[0].title).toBe("Song 1");
    });
  });
});
```

---

## 5.8 Testes de Containers

**Arquivo**: `frontend/src/containers/DiscoverContainer.test.jsx`

```javascript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DiscoverContainer from "./DiscoverContainer";

describe("DiscoverContainer", () => {
  it("should render Discover page with hook state", () => {
    render(<DiscoverContainer />);
    
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /search/i })).toBeInTheDocument();
  });

  it("should call hook search on form submit", async () => {
    const { getByPlaceholderText, getByRole } = render(<DiscoverContainer />);
    
    const input = getByPlaceholderText(/search/i);
    const button = getByRole("button", { name: /search/i });
    
    // User types and submits
    fireEvent.change(input, { target: { value: "rock music" } });
    fireEvent.click(button);
    
    // Verify hook state updated (would need integration)
  });
});
```

---

## 5.9 Executar Testes

### Backend

```bash
# Compilar checks
python -m compileall app/

# Rodar testes
cd backend
pytest tests/ -v --cov=app --cov-report=html

# Gerar relatório
# Relatório HTML em htmlcov/index.html
```

### Frontend

```bash
cd frontend
npm run test          # Rodar tests
npm run test:coverage # Gerar cobertura
```

---

## 5.10 Critérios de Conclusão

- [ ] Backend: ≥70% coverage de novo código (repositories, use cases)
- [ ] Backend: Todos testes passam (`pytest tests/` → 0 failures)
- [ ] Frontend: Hooks têm testes básicos
- [ ] Frontend: Containers têm testes básicos
- [ ] Frontend: `npm run test` passa sem erros
- [ ] Cobertura relatório gerado (HTML)
- [ ] CI/CD (opcional): GitHub Actions rodando testes em PR

---

## Próximas Ações

Fase 5 completa → Fase 6 (consolidação final)

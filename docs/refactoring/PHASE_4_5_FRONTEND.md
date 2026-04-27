# Fases 4-5: Refatoração Frontend

## Fase 4: Extrair Hooks por Domínio

**Duração**: 2-3 dias  
**Objetivo**: Mover lógica de `App.jsx` para hooks reutilizáveis  
**Saída**: Hooks isolados, App mais simples, funcionalidade inalterada

---

### Contexto

`App.jsx` hoje gerencia: roteamento, estado de sessão, busca, processamento, biblioteca, workspace, exportação. Isso tudo em ~1200 linhas.

Vamos extrair em 5 hooks principais:

```
useDiscovery()      → Gerencia busca, seleção de candidatos
useSession()        → Gerencia sessão ativa, job atual
useLibrary()        → Gerencia lista de sessões, filtros, paginação
useWorkspace()      → Gerencia mix-state, player, exportação
useProcessing()     → Gerencia progresso, eventos, WebSocket
```

---

### Estrutura Alvo

```
frontend/src/
├── hooks/
│   ├── useDiscovery.js      # (search, candidates, selection)
│   ├── useSession.js        # (current session, job tracking)
│   ├── useLibrary.js        # (list, filters, pagination)
│   ├── useWorkspace.js      # (mix-state, player, export)
│   ├── useProcessing.js     # (progress, events, WebSocket)
│   └── useCommonState.js    # (shared converters, formatters)
├── pages/
│   ├── DiscoverPage.jsx     # (apenas apresentação)
│   ├── SessionPage.jsx      # (apenas apresentação)
│   ├── WorkspacePage.jsx    # (apenas apresentação)
│   └── LibraryPage.jsx      # (apenas apresentação)
├── containers/
│   ├── DiscoverContainer.jsx    # (page + hook)
│   ├── SessionContainer.jsx     # (page + hook)
│   ├── WorkspaceContainer.jsx   # (page + hook)
│   └── LibraryContainer.jsx     # (page + hook)
├── App.jsx                  # (shell + routing)
└── ...
```

---

### 4.1 useDiscovery Hook

**Arquivo**: `frontend/src/hooks/useDiscovery.js`

```javascript
import { useState } from "react";
import { searchCandidates } from "../api";

export function useDiscovery() {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  const runSearch = async (queryValue = query.trim()) => {
    setError("");

    if (queryValue.length < 3) {
      setError("Informe ao menos 3 caracteres");
      return null;
    }

    try {
      setSearching(true);
      const response = await searchCandidates(queryValue, 5);
      const nextCandidates = response.candidates || [];
      const recommendedSourceId =
        response.recommended_source_id || nextCandidates[0]?.source_id || "";

      setCandidates(nextCandidates);
      setSelectedSourceId(recommendedSourceId);
      setLastSearchQuery(queryValue);

      if (!nextCandidates.length) {
        setError("Nenhum resultado encontrado");
      }
      return response;
    } catch (err) {
      setError(err.message || "Falha ao buscar");
      return null;
    } finally {
      setSearching(false);
    }
  };

  const selectedCandidate = candidates.find(
    (c) => c.source_id === selectedSourceId
  ) || null;

  return {
    query,
    setQuery,
    candidates,
    selectedSourceId,
    setSelectedSourceId,
    searching,
    error,
    runSearch,
    selectedCandidate,
    lastSearchQuery,
  };
}
```

---

### 4.2 useSession Hook

**Arquivo**: `frontend/src/hooks/useSession.js`

```javascript
import { useState } from "react";
import { getSession, getSessionEvents, connectJobSocket } from "../api";

export function useSession() {
  const [currentSession, setCurrentSession] = useState({
    session_id: "",
    session_code: "",
    job_id: "",
    status: "idle",
  });
  const [sessionEvents, setSessionEvents] = useState([]);
  const [sessionEventsLoading, setSessionEventsLoading] = useState(false);
  const [sessionEventsError, setSessionEventsError] = useState("");

  const fetchSessionEvents = async (sessionId, options = {}) => {
    const { silent = false } = options;
    if (!sessionId) return;

    if (!silent) setSessionEventsLoading(true);
    setSessionEventsError("");

    try {
      const events = await getSessionEvents(sessionId);
      setSessionEvents(Array.isArray(events) ? events : []);
    } catch (err) {
      setSessionEventsError(err.message || "Falha ao carregar eventos");
    } finally {
      if (!silent) setSessionEventsLoading(false);
    }
  };

  const hydratSessionAndNavigate = async (sessionId, targetPage) => {
    if (!sessionId) return;

    try {
      const detail = await getSession(sessionId);
      setCurrentSession({
        session_id: detail.session_id,
        session_code: detail.session_code,
        job_id: detail.session_id,
        status: detail.status,
      });
      await fetchSessionEvents(detail.session_id);
    } catch (err) {
      setSessionEventsError(err.message || "Falha ao abrir sessão");
    }
  };

  return {
    currentSession,
    setCurrentSession,
    sessionEvents,
    sessionEventsLoading,
    sessionEventsError,
    fetchSessionEvents,
    hydratSessionAndNavigate,
  };
}
```

---

### 4.3 useLibrary Hook

**Arquivo**: `frontend/src/hooks/useLibrary.js`

```javascript
import { useState } from "react";
import { listSessions, duplicateSession, reprocessSession } from "../api";

const LIBRARY_PAGE_SIZE = 8;

export function useLibrary() {
  const [filters, setFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [appliedFilters, setAppliedFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState({ items: [], total: 0, page: 1, page_size: LIBRARY_PAGE_SIZE });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const fetchSessions = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await listSessions({
        query: appliedFilters.query.trim() || undefined,
        status: appliedFilters.status || undefined,
        page,
        page_size: LIBRARY_PAGE_SIZE,
      });
      setPayload(response);
    } catch (err) {
      setError(err.message || "Falha ao carregar sessões");
    } finally {
      setLoading(false);
    }
  };

  const handleDuplicate = async (sessionId) => {
    setActionLoading(`duplicate:${sessionId}`);
    setError("");

    try {
      const response = await duplicateSession(sessionId);
      setActionMessage(`Sessão duplicada`);
      await fetchSessions();
    } catch (err) {
      setError(err.message || "Falha ao duplicar");
    } finally {
      setActionLoading("");
    }
  };

  const handleReprocess = async (sessionId) => {
    setActionLoading(`reprocess:${sessionId}`);
    setError("");

    try {
      await reprocessSession(sessionId);
      setActionMessage(`Reprocessamento iniciado`);
      await fetchSessions();
    } catch (err) {
      setError(err.message || "Falha ao reprocessar");
    } finally {
      setActionLoading("");
    }
  };

  const totalPages = Math.max(
    1,
    Math.ceil((payload.total || 0) / (payload.page_size || LIBRARY_PAGE_SIZE))
  );

  return {
    filters,
    setFilters,
    appliedFilters,
    setAppliedFilters,
    page,
    setPage,
    payload,
    loading,
    error,
    actionLoading,
    actionMessage,
    totalPages,
    fetchSessions,
    handleDuplicate,
    handleReprocess,
  };
}
```

---

### 4.4 useWorkspace Hook

**Arquivo**: `frontend/src/hooks/useWorkspace.js`

```javascript
import { useState, useEffect, useRef } from "react";
import { getMixState, updateMixState, createExportJob, listExportJobs } from "../api";

const DEFAULT_MIX_LEVELS = {
  vocals: 84,
  drums: 72,
  bass: 65,
  other: 58,
  master: 78,
};

export function useWorkspace() {
  const [mixLevels, setMixLevels] = useState(DEFAULT_MIX_LEVELS);
  const [mixStateLoading, setMixStateLoading] = useState(false);
  const [mixStateSaving, setMixStateSaving] = useState(false);
  const [mixStateError, setMixStateError] = useState("");
  const [exportJobs, setExportJobs] = useState([]);
  const [exportJobsLoading, setExportJobsLoading] = useState(false);
  const [exportJobsError, setExportJobsError] = useState("");
  const [exportActionLoading, setExportActionLoading] = useState("");
  const [exportActionMessage, setExportActionMessage] = useState("");
  
  const loadedMixSessionRef = useRef("");
  const mixSaveTimerRef = useRef(null);
  const lastPersistedMixRef = useRef("");

  const fetchMixState = async (sessionId) => {
    if (!sessionId || loadedMixSessionRef.current === sessionId) return;

    setMixStateLoading(true);
    setMixStateError("");

    try {
      const response = await getMixState(sessionId);
      // Converter response para levels (simplificado)
      setMixLevels(DEFAULT_MIX_LEVELS);
      loadedMixSessionRef.current = sessionId;
    } catch (err) {
      setMixStateError(err.message || "Falha ao carregar mix-state");
    } finally {
      setMixStateLoading(false);
    }
  };

  const saveMixState = async (sessionId, levels) => {
    if (!sessionId) return;

    setMixStateSaving(true);
    setMixStateError("");

    try {
      const payload = { per_stem: {}, master_gain: levels.master };
      await updateMixState(sessionId, payload);
      lastPersistedMixRef.current = JSON.stringify(levels);
    } catch (err) {
      setMixStateError(err.message || "Falha ao salvar mix-state");
    } finally {
      setMixStateSaving(false);
    }
  };

  const fetchExports = async (sessionId) => {
    if (!sessionId) return;

    setExportJobsLoading(true);
    setExportJobsError("");

    try {
      const jobs = await listExportJobs(sessionId);
      setExportJobs(Array.isArray(jobs) ? jobs : []);
    } catch (err) {
      setExportJobsError(err.message || "Falha ao carregar exportações");
    } finally {
      setExportJobsLoading(false);
    }
  };

  const createExport = async (sessionId, preset, format) => {
    if (!sessionId) return;

    setExportActionLoading(`${preset}:${format}`);
    setExportJobsError("");

    try {
      await createExportJob(sessionId, { preset, format });
      setExportActionMessage(`Exportação ${preset} iniciada`);
      await fetchExports(sessionId);
    } catch (err) {
      setExportJobsError(err.message || "Falha ao criar exportação");
    } finally {
      setExportActionLoading("");
    }
  };

  return {
    mixLevels,
    setMixLevels,
    mixStateLoading,
    mixStateSaving,
    mixStateError,
    exportJobs,
    exportJobsLoading,
    exportJobsError,
    exportActionLoading,
    exportActionMessage,
    fetchMixState,
    saveMixState,
    fetchExports,
    createExport,
  };
}
```

---

### 4.5 useProcessing Hook

**Arquivo**: `frontend/src/hooks/useProcessing.js`

```javascript
import { useState, useRef } from "react";
import { connectJobSocket } from "../api";

const FINAL_STATES = new Set(["ready", "failed"]);

export function useProcessing() {
  const [processing, setProcessing] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  
  const jobSocketRef = useRef(null);

  const closeSocket = () => {
    if (jobSocketRef.current) {
      jobSocketRef.current.close();
      jobSocketRef.current = null;
    }
  };

  const startTracking = (jobId) => {
    if (!jobId) return;

    closeSocket();
    jobSocketRef.current = connectJobSocket(
      jobId,
      (payload) => {
        setJob(payload);
        if (FINAL_STATES.has(payload.state)) {
          closeSocket();
          setProcessing(false);
        }
      },
      () => {
        setError("Falha na conexão de progresso");
        setProcessing(false);
      }
    );
  };

  return {
    processing,
    setProcessing,
    job,
    setJob,
    error,
    setError,
    startTracking,
    closeSocket,
  };
}
```

---

## Fase 5: Simplificar App.jsx

**Duração**: 1-2 dias  
**Objetivo**: Reduzir `App.jsx` de 1200+ linhas para ~200 (shell + roteamento)  
**Saída**: App apenas com navegação e provider, lógica em containers/hooks

---

### 5.1 Criar App Shell Simples

**Arquivo**: `frontend/src/App.jsx`

```javascript
import { useState } from "react";
import { PAGES } from "./constants";
import DiscoverContainer from "./containers/DiscoverContainer";
import SessionContainer from "./containers/SessionContainer";
import WorkspaceContainer from "./containers/WorkspaceContainer";
import LibraryContainer from "./containers/LibraryContainer";

export default function App() {
  const [currentPage, setCurrentPage] = useState(PAGES.discover);

  return (
    <main className="page-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setCurrentPage(PAGES.discover)}>
          <span className="brand-badge">MX</span>
          <span className="brand-title">
            <strong>Music Analyzer</strong>
            <span>Studio Workspace</span>
          </span>
        </button>

        <nav className="nav-links">
          <button
            className={`nav-link-btn ${currentPage === PAGES.discover ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.discover)}
          >
            Descobrir
          </button>
          <button
            className={`nav-link-btn ${currentPage === PAGES.session ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.session)}
          >
            Processamento
          </button>
          <button
            className={`nav-link-btn ${currentPage === PAGES.workspace ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.workspace)}
          >
            Workspace
          </button>
          <button
            className={`nav-link-btn ${currentPage === PAGES.library ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.library)}
          >
            Biblioteca
          </button>
        </nav>
      </header>

      {currentPage === PAGES.discover && <DiscoverContainer />}
      {currentPage === PAGES.session && <SessionContainer />}
      {currentPage === PAGES.workspace && <WorkspaceContainer />}
      {currentPage === PAGES.library && <LibraryContainer />}
    </main>
  );
}
```

---

### 5.2 Criar Containers (Page Logic)

**Arquivo**: `frontend/src/containers/DiscoverContainer.jsx`

```javascript
import { useDiscovery } from "../hooks/useDiscovery";
import DiscoverPage from "../pages/DiscoverPage";

export default function DiscoverContainer() {
  const discovery = useDiscovery();

  const handleSubmit = async (event) => {
    event.preventDefault();
    // Lógica de submissão que antes estava em App
  };

  return (
    <DiscoverPage
      {...discovery}
      handleSubmit={handleSubmit}
      // ... props que Page espera
    />
  );
}
```

---

## Checklist de Conclusão das Fases 4-5

**Fase 4**:
- [ ] 5 hooks criados (Discovery, Session, Library, Workspace, Processing)
- [ ] Cada hook é reutilizável e testável
- [ ] Testes básicos de hook passam
- [ ] App.jsx ainda compila mas sem usar hooks novos

**Fase 5**:
- [ ] App.jsx reduzido a shell (~200 linhas)
- [ ] 4 containers criados (Discover, Session, Workspace, Library)
- [ ] Cada página recebe props apenas dos containers
- [ ] Funcionalidade inalterada
- [ ] No build errors
- [ ] Smoke test de navegação passa

---

## Próximas Fases

Fase 6 vai consolidar testes e validações para garantir que refatoração não quebrou nada.

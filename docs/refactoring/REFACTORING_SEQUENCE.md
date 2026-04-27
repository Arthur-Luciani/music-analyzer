# Refatoração Music Analyzer: Sequência Completa de Implementação

**Status**: Fases 0-5 planejadas. Fase 0 parcialmente completa (SessionRepository extraído).

---

## 1. Resumo Executivo

### Situação Atual
- Backend: 1500+ linhas em um único `JobService` (god service)
- Frontend: 1200+ linhas em `App.jsx` (god component)
- Persistência: SQLite3 com `SQLiteSessionStore` (extraído em Fase 0)
- Testes: Nenhum; refatoração sem rede de segurança

### Objetivo
Reorganizar codebase em camadas limpas (layered architecture):
1. **Domain Layer**: Modelos (Pydantic → SQLAlchemy)
2. **Data Layer**: Repositórios (SQLite → ORM)
3. **Application Layer**: Use cases (business logic isolada)
4. **Presentation Layer**: Routes (HTTP contract)
5. **Frontend**: Hooks + containers (state decomposed)

### Benefícios Esperados
- ✅ Código testável (unit test cada use case isolado)
- ✅ Manutenível (adicionar feature = novo use case)
- ✅ Evoluível (trocar DB sem alterar lógica)
- ✅ Escalável (ORM com migrations; async/await)

---

## 2. Roadmap Completo (6 Fases)

### Fase 0: Extraction (PARCIALMENTE COMPLETA)

**O que foi feito**:
- ✅ SQLiteSessionStore extraído de jobs.py → backend/app/repositories/session_store.py (626 linhas)
- ✅ Import atualizado em jobs.py (linha 20)
- ✅ Compilação validada
- ✅ Smoke test passou (session create/list/load)

**O que falta**:
- 🔄 Remover duplicate SQLiteSessionStore de jobs.py (linhas 27-660, agora dead code)
- 🔄 Criar backend/app/repositories/__init__.py com exports

**Duração**: 30 minutos

---

### Fase 1: ORM Setup

**Objetivo**: Preparar infraestrutura de dados para ORM

**Passos**:
1. Instalar dependências: `SQLAlchemy 2.x`, `Alembic`, `asyncpg` (opcional)
2. Criar backend/app/models.py com SQLAlchemy declarative base
3. Migrar Pydantic models para SQLAlchemy (híbrido: response models + ORM models)
4. Inicializar Alembic: `alembic init alembic`
5. Criar primeira migration: `alembic revision --autogenerate -m "initial_schema"`
6. Testar migração em banco de testes

**Entrada**: backend/app/repositories/session_store.py (SQLite schema)

**Saída**: 
- SQLAlchemy models (backend/app/models_orm.py ou estendido em models.py)
- Alembic migrations/ directory com schema version control

**Duração**: 1 dia

**Risco**: ORM migration pode quebrar queries; validação intensiva necessária.

---

### Fase 2: ORM Migration

**Objetivo**: Reescrever camada de dados com ORM, manter backend funcionando

**Passos**:
1. Criar backend/app/repositories/session_repository.py (ORM-based)
   - Reescrever métodos de SessionStore usando SQLAlchemy queries
   - Manter mesma interface pública
2. Atualizar imports em jobs.py: trocar SQLiteSessionStore por SessionRepository
3. Rodar testes de repositório
4. Validar que jobs.py não quebrou

**Entrada**: Fase 1 (ORM models + Alembic setup)

**Saída**:
- backend/app/repositories/session_repository.py (200-300 linhas)
- jobs.py atualizado (import)
- Alembic migration executada

**Duração**: 1-2 dias

**Risco**: Query syntax diferente; N+1 queries; transaction boundaries.

---

### Fase 3: Use Cases (Application Layer)

**Objetivo**: Extrair business logic de JobService em classes reutilizáveis

**Use Cases**:
1. `SearchTracksUseCase`: YouTube search → candidates
2. `ProcessJobUseCase`: Orquestra pipeline (download → separate → analyze)
3. `DuplicateSessionUseCase`: Clone existing session
4. `ExportUseCase`: Gera export (WAV mixed ou ZIP stems)
5. `MixStateUseCase`: Save/load mix-state

**Passos**:
1. Criar backend/app/application/ directory
2. Cada use case em seu arquivo (5 arquivos × ~100-150 linhas)
3. Cada recebe SessionRepository injetado
4. Atualizar main.py routes para instantiate use cases
5. Deletar métodos de JobService que viraram use cases

**Entrada**: Fase 2 (ORM repositories)

**Saída**:
- backend/app/application/ com 5 use case files
- main.py routes refatoradas (menos lógica, mais orquestração)
- JobService reduzido (apenas WebSocket broadcasting?)

**Duração**: 2-3 dias

**Risco**: Use case responsibilities não bem definidas; transaction boundaries complexas.

---

### Fase 4-5: Frontend Refactoring

**Objetivo**: Extrair lógica de App.jsx em hooks, simplificar componentes

**Hooks** (5 total):
1. `useDiscovery()`: search + candidates
2. `useSession()`: current session tracking
3. `useLibrary()`: sessions list + filters
4. `useWorkspace()`: mix-state + exports
5. `useProcessing()`: WebSocket + job progress

**Estrutura**:
```
frontend/
├── hooks/
│   ├── useDiscovery.js
│   ├── useSession.js
│   ├── useLibrary.js
│   ├── useWorkspace.js
│   └── useProcessing.js
├── containers/
│   ├── DiscoverContainer.jsx
│   ├── SessionContainer.jsx
│   ├── WorkspaceContainer.jsx
│   └── LibraryContainer.jsx
├── pages/
│   ├── DiscoverPage.jsx      (presentation only)
│   ├── SessionPage.jsx       (presentation only)
│   ├── WorkspacePage.jsx     (presentation only)
│   └── LibraryPage.jsx       (presentation only)
└── App.jsx                   (shell: routing only)
```

**Duração**: 2-3 dias

**Saída**:
- App.jsx reduzido de 1200+ → 200 linhas (apenas shell)
- 5 custom hooks criados
- 4 container components criados
- Pages agora apenas presentation (Dumb Components)

---

### Fase 5: Test Coverage

**Objetivo**: Criar testes para código novo, validar refatoração não quebrou nada

**Cobertura alvo**: ≥70% de novo código

**Backend testes**:
- Repositories (session_store, session_repository)
- Use cases (5 use cases)
- Routes (main endpoints)

**Frontend testes**:
- Hooks (vitest + React Testing Library)
- Containers
- Pages (básico)

**Duração**: 3-4 dias

**Saída**:
- backend/tests/ directory com >50 testes
- frontend/src/**/*.test.jsx com >30 testes
- Coverage reports (HTML)
- CI/CD setup (opcional: GitHub Actions)

---

### Fase 6: Consolidação & Cleanup

**Objetivo**: Remover dead code, documentar nova arquitetura, otimizar

**Passos**:
1. Deletar código dead (legacy SQLiteSessionStore em jobs.py)
2. Normalizar imports e paths
3. Documentar arquitetura no README
4. Performance profiling (se necessário)
5. Deploy em staging, validar smoke tests

**Duração**: 1 dia

**Saída**:
- Codebase limpo, pronto para feature development
- Arquitetura documentada
- Refatoração completada

---

## 3. Dependências Entre Fases

```
Fase 0: Extraction
    ↓
Fase 1: ORM Setup
    ↓
Fase 2: ORM Migration
    ↓
Fase 3: Use Cases
    ↓
Fase 4-5: Frontend (pode iniciar após Fase 3 API estável)
    ↓
Fase 5: Tests (melhor após Fases 3-4 completas)
    ↓
Fase 6: Consolidation
```

**Caminho crítico**: Fases 0 → 1 → 2 → 3 (backend) + 4-5 (frontend em paralelo após Fase 3)

**Parallelização possível**:
- Fases 4-5 podem iniciar enquanto Fase 3 está em 80% (API contratos já definidos)
- Fase 5 testes podem iniciar assim que código novo da Fase 3 + 4 está 50% pronto

---

## 4. Arquivos Criados Até Agora

Documentação de planejamento (todas em docs/):

1. ✅ docs/REFACTORING_MASTER_PLAN.md
   - 6 fases de alto nível
   - Riscos, dependências, saídas esperadas

2. ✅ docs/PHASE_1_ORM_SETUP.md
   - SQLAlchemy + Alembic setup
   - Migração de schema
   - Especificação de models

3. ✅ docs/PHASE_2_ORM_MIGRATION.md
   - SessionRepository reimplementação
   - Alembic migrations
   - Backward compatibility

4. ✅ docs/PHASE_3_USE_CASES.md
   - 5 use cases especificadas
   - Dependency injection
   - Transaction boundaries

5. ✅ docs/PHASE_4_5_FRONTEND.md
   - 5 hooks + estrutura de containers
   - Code snippets prontos
   - Checklist de conclusão

6. ✅ docs/PHASE_5_TEST_COVERAGE.md
   - Setup pytest + vitest
   - Fixtures compartilhadas
   - Testes de exemplo (repos, use cases, hooks)

---

## 5. Estado da Implementação

### Backend - Fase 0 (Em Progresso)

**✅ Completo**:
- SessionRepository extraído para backend/app/repositories/session_store.py
- Compilação validada (python -m compileall)
- Smoke test passou

**🔄 Pendente**:
- Remover duplicate SQLiteSessionStore de jobs.py
- Criar __init__.py em repositories/

**Próximo passo**:
```bash
# 1. Remover linhas 27-660 de backend/app/services/jobs.py
# 2. Criar backend/app/repositories/__init__.py
# 3. Run again: python -m compileall app/
```

---

### Backend - Fases 1-3

**Documentação**: Completa (PHASE_1_ORM_SETUP.md + PHASE_2_ORM_MIGRATION.md + PHASE_3_USE_CASES.md)

**Status**: Pronto para iniciar

**Próximo step**:
```bash
# Inicia Fase 1 quando Fase 0 completa
pip install sqlalchemy alembic
# ... seguir PHASE_1_ORM_SETUP.md passo a passo
```

---

### Frontend - Fases 4-5

**Documentação**: Completa (PHASE_4_5_FRONTEND.md + PHASE_5_TEST_COVERAGE.md)

**Status**: Pronto para iniciar após Fase 3 API estável

**Próximo step**:
```bash
# Inicia Fase 4 quando:
# 1. Fase 3 use cases API estabilizada
# 2. main.py routes atualizados
cd frontend
npm install --save-dev @testing-library/react vitest
# ... seguir PHASE_4_5_FRONTEND.md
```

---

## 6. Checklist Imediato (Próximas 2 horas)

- [ ] Remover duplicate SQLiteSessionStore de jobs.py (linhas 27-660)
- [ ] Criar backend/app/repositories/__init__.py
- [ ] Run `python -m compileall app/` → 0 errors
- [ ] Run smoke test novamente
- [ ] Commit: "Cleanup Phase 0: Remove duplicate SQLiteSessionStore"

---

## 7. Timeline Realista

Assumindo ~4 horas/dia de dedição:

| Fase | Duração | Datas (começando hoje) |
|------|---------|------------------------|
| 0 (cleanup) | 0.5h | Hoje |
| 1 (ORM setup) | 1 dia | Amanhã |
| 2 (ORM migration) | 2 dias | Dia 3-4 |
| 3 (use cases) | 3 dias | Dia 5-7 |
| 4 (frontend hooks) | 2 dias | Dia 5-6 (paralelo com Fase 3) |
| 5 (tests) | 4 dias | Dia 8-11 |
| 6 (consolidation) | 1 dia | Dia 12 |
| **Total** | **~13 dias** | **~2 semanas** |

---

## 8. Referências Rápidas

### Documentação Criada
- Master plan: docs/REFACTORING_MASTER_PLAN.md
- Fase 1: docs/PHASE_1_ORM_SETUP.md
- Fase 2: docs/PHASE_2_ORM_MIGRATION.md
- Fase 3: docs/PHASE_3_USE_CASES.md
- Fases 4-5: docs/PHASE_4_5_FRONTEND.md
- Fases 5 testes: docs/PHASE_5_TEST_COVERAGE.md

### Code Locations
- Backend: c:\git\music-analyzer\backend\
- Frontend: c:\git\music-analyzer\frontend\
- Storage: c:\git\music-analyzer\storage\
- Current SessionRepository: backend/app/repositories/session_store.py

### Key Files to Monitor
- backend/app/services/jobs.py (será refatorado Fases 1-3)
- backend/app/main.py (será refatorado Fase 3)
- frontend/src/App.jsx (será refatorado Fases 4-5)

---

## 9. Próximas Ações

### Imediato (Hoje)
1. Remover duplicate SQLiteSessionStore de jobs.py
2. Commit & validate

### Curto Prazo (Próx. 3 dias)
1. Iniciar Fase 1 (ORM setup)
2. Criar SQLAlchemy models
3. Inicializar Alembic

### Médio Prazo (Próx. 1-2 semanas)
1. Completar Fases 2-3 (ORM + Use cases)
2. Iniciar Fases 4-5 (Frontend + Tests)
3. Consolidação final

---

## 10. Notas Importantes

### Backward Compatibility
- Todas mudanças são internas (API contracts mantidos)
- Frontend não precisa mudar até Fase 4
- Funcionalidade MVP preservada integralmente

### Rollback Strategy
- Cada fase é self-contained; rollback simples (git revert)
- Testes validam nenhuma regressão
- DB schema versioned via Alembic

### Performance Considerations
- ORM pode adicionar overhead; profiling na Fase 6
- Async/await já presente; aproveitar com SQLAlchemy asyncio
- Use cases podem cache; Redis opcional later

### Testing Strategy
- Unit tests: use cases (mocked repos)
- Integration tests: repos (real DB)
- E2E tests: routes (test client)
- Frontend tests: hooks (React Testing Library)

---

## 11. Suporte & Referências

### Arquitetura Adotada
- **Pattern**: Layered Architecture (Domain, Data, Application, Presentation)
- **Backend DDD**: Use cases = application layer; repositories = data layer
- **Frontend**: Container/Presentation pattern

### Frameworks
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic, Alembic
- Frontend: React 18, Vite, custom hooks

### Best Practices
- SOLID principles (Single responsibility)
- Separation of concerns
- Dependency injection
- Testability first

---

**Documento Criado**: 2026-04-19  
**Última Atualização**: Fases 0-5 documentadas, Fase 0 parcialmente implementada  
**Status**: Pronto para implementação de Fases 1-6


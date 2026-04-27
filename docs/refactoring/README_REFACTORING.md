# Sumário da Refatoração Music Analyzer

**Data**: 19 de Abril de 2026  
**Status**: Fases 0-5 completamente planejadas. Fase 0 em execução.

---

## O Problema

**Backend** (jobs.py):
- 1500+ linhas em um único arquivo (`JobService` = god service)
- Mistura YouTube search, Demucs orchestration, SQLite, FFmpeg, WebSocket
- Impossível testar componentes isolados
- Difícil adicionar features sem quebrar algo

**Frontend** (App.jsx):
- 1200+ linhas em um único arquivo
- Estado misturado (search, session, mix-state, exports)
- 30+ useState e useEffect entrelaçados
- Pages recebem 50+ props

---

## A Solução em 6 Fases

### Fase 0: Limpeza (FAZENDO AGORA)
**O que**: Extrair camada de persistência  
**Como**: SQLiteSessionStore saiu de jobs.py → novo arquivo  
**Status**: ✅ Extraído, ⏳ Precisa remover duplicate de jobs.py  
**Tempo**: 30 min  

```
Antes:
backend/app/services/jobs.py (1500+ linhas)
  ├── SQLiteSessionStore (626 linhas)
  └── JobService (874+ linhas)

Depois:
backend/app/repositories/
  └── session_store.py (626 linhas)
backend/app/services/jobs.py
  └── JobService apenas (874 linhas, mais limpo)
```

### Fase 1: Infraestrutura de Dados (1 dia)
**O que**: Preparar ORM (SQLAlchemy 2.x)  
**Como**:
- Instalar SQLAlchemy + Alembic
- Criar models ORM
- Inicializar versionamento de schema (Alembic)

**Por que**: Separar "como os dados são armazenados" da "lógica de negócio"

### Fase 2: Migração de Dados (2 dias)
**O que**: Reescrever SessionRepository com ORM  
**Como**:
- Converter queries SQLite3 → SQLAlchemy
- Executar Alembic migration
- Validar que JobService ainda funciona

**Por que**: Agora banco de dados é abstração; lógica de negócio não sabe de SQL

### Fase 3: Lógica de Negócio (3 dias)
**O que**: Extrair use cases de JobService  
**Como**: Criar 5 arquivos (search, process, duplicate, export, mix-state)

```
Antes:
JobService.search() → YouTube search + yt-dlp + scoring
JobService.create_job() → Download + Demucs + análise
JobService.export() → FFmpeg mixing + zip

Depois:
SearchTracksUseCase.execute()
ProcessJobUseCase.execute()
ExportUseCase.execute()
...

Cada um pode ser testado isolado!
```

**Por que**: Código testável, reutilizável, manutenível

### Fase 4: Frontend Hooks (2 dias)
**O que**: Decompor App.jsx em hooks reutilizáveis  
**Como**: Criar 5 hooks (Discovery, Session, Library, Workspace, Processing)

```
Antes:
App.jsx (1200 linhas)
  ├── 30+ useState
  ├── 8+ useEffect
  ├── Timers, WebSocket, API calls
  └── Passa 50+ props para pages

Depois:
useDiscovery()      → search + candidates
useSession()        → session tracking
useLibrary()        → sessions list
useWorkspace()      → mix-state + export
useProcessing()     → WebSocket + progress

App.jsx (200 linhas)
  └── Apenas roteamento
```

**Por que**: Pages ficam simples (dumb components), lógica fica testável

### Fase 5: Testes (4 dias)
**O que**: Cobertura de testes >70%  
**Como**:
- Backend: pytest para use cases + repositories
- Frontend: vitest para hooks + containers

**Por que**: Segurança ao refatorar; confiança no código novo

### Fase 6: Consolidação (1 dia)
**O que**: Limpeza final  
**Como**:
- Remover código morto
- Documentar arquitetura
- Deploy em staging

**Por que**: Codebase limpo, pronto para feature development

---

## Timeline

```
Hoje:          Fase 0 (cleanup)        ████ 30min
Amanhã:        Fase 1 (ORM setup)      ████████████ 1 dia
Dia 3-4:       Fase 2 (ORM migration)  ████████████████████████ 2 dias
Dia 5-7:       Fase 3 (use cases)      ████████████████████████████████████ 3 dias
Dia 5-6:       Fase 4 (frontend)       ████████████████████████ 2 dias (paralelo)
Dia 8-11:      Fase 5 (testes)         ████████████████████████████████████████ 4 dias
Dia 12:        Fase 6 (cleanup)        ████████████ 1 dia

Total: ~2 semanas (13 dias)
```

---

## Arquivos Criados Hoje

Toda documentação técnica está em `docs/`:

1. **REFACTORING_MASTER_PLAN.md** - Visão geral de 6 fases
2. **PHASE_1_ORM_SETUP.md** - Instruções específicas para Fase 1
3. **PHASE_2_ORM_MIGRATION.md** - Instruções para Fase 2
4. **PHASE_3_USE_CASES.md** - Especificação de use cases
5. **PHASE_4_5_FRONTEND.md** - Hooks + containers code snippets
6. **PHASE_5_TEST_COVERAGE.md** - Testes de exemplo + setup
7. **REFACTORING_SEQUENCE.md** - Sequência completa + dependências

---

## Próximos Passos Imediatos

### Hoje (Fase 0 - Cleanup)

```bash
# 1. Remover linhas 27-660 de backend/app/services/jobs.py
#    (SQLiteSessionStore duplicado, agora em repositories/session_store.py)

# 2. Certificar que backend compila sem errors
cd backend
python -m compileall app/

# 3. Rodar smoke test para garantir que nada quebrou
python -c "
from app.services.jobs import JobService
from app.settings import settings
js = JobService(settings.sessions_db_path)
code = js.create_session()
print(f'✅ Session created: {code}')
sessions = js.list_sessions()
print(f'✅ Sessions listed: {len(sessions)} found')
"

# 4. Commit & push
git add -A
git commit -m "Phase 0: Remove duplicate SQLiteSessionStore from jobs.py"
```

### Amanhã (Fase 1 - ORM Setup)

```bash
# Ler e seguir: docs/PHASE_1_ORM_SETUP.md

pip install sqlalchemy alembic
# ... criar models SQLAlchemy
# ... inicializar Alembic
```

---

## Garantias

✅ **Nenhuma funcionalidade se perde**  
Tudo que funciona hoje vai funcionar depois.

✅ **API não muda**  
Frontend não precisa mudar até Fase 4.

✅ **Rollback simples**  
Cada fase é independente. Se quebrar, `git revert`.

✅ **Sem downtime**  
Refatoração interna; deploy transparente.

---

## Perguntas Frequentes

**P: Precisa fazer todas as 6 fases?**  
R: Idealmente sim, mas pode parar em qualquer ponto. Fases 1-3 melhoram backend bastante; Fases 4-5 melhoram frontend.

**P: E se algo quebrar?**  
R: Cada fase tem smoke tests. Se quebrar, rollback é simples (git revert + restaurar DB backup).

**P: Pode fazer em paralelo?**  
R: Sim! Fases 4-5 (frontend) podem rodar enquanto Fase 3 (backend) está 80% pronta.

**P: Quanto tempo leva?**  
R: ~2 semanas full-time (~4h/dia = ~4 semanas).

**P: Precisa parar o projeto?**  
R: Não. Desenvolvimento de features pode continuar em branch. Merge quando Fase 6 completa.

---

## Contato & Suporte

Se tiver dúvidas:
1. Ler o arquivo de fase específica (docs/PHASE_X_...)
2. Checar REFACTORING_SEQUENCE.md para contexto
3. Validar com smoke test após cada change

---

**Preparado por**: GitHub Copilot  
**Modelo**: Claude Haiku 4.5  
**Próxima revisão**: Após Fase 0 completa

# Plano Mestre de Refatoração - Music Analyzer

**Data**: 27 de abril de 2026  
**Status**: Em execução  
**Objetivo**: Reduzir dívida técnica preservando 100% do MVP funcional

---

## Visão Geral

O projeto tem um MVP funcional com backend FastAPI e frontend React, mas concentra responsabilidades em dois pontos únicos de falha: `jobs.py` no backend e `App.jsx` no frontend. O plano de refatoração divide a reorganização em fases executáveis, integrando uma migração para ORM leve a fim de preparar o backend para crescimento sustentável.

### Princípios

- **Preservar MVP**: Nenhuma mudança deve quebrar a funcionalidade atual.
- **Incrementalismo**: Fatias verticais pequenas, validadas antes de prosseguir.
- **Testabilidade**: Cada camada deve ser testável isoladamente.
- **Simplicidade**: Adicionar estrutura apenas onde há complexidade real.

---

## Fases de Execução

| Fase | Área | Descrição | Duração Est. | Validação |
|------|------|-----------|--------------|-----------|
| 0 | Backend | Extrair repositório SQLite (concluída) | ✓ | Smoke test |
| 1 | Backend | Introduzir ORM leve (SQLAlchemy 2.x) | 2-3 dias | Testes de persistência |
| 2 | Backend | Migrar tabelas para ORM e Alembic | 3-4 dias | Testes de contrato API |
| 3 | Backend | Refatorar JobService em casos de uso | 2-3 dias | Testes de fluxo |
| 4 | Frontend | Extrair hooks por domínio | 2-3 dias | Testes de integração UI |
| 5 | Frontend | Simplificar App.jsx em shell | 1-2 dias | Testes de navegação |
| 6 | Full | Consolidar testes e validações | 2-3 dias | QA fim-a-fim |

**Total estimado**: 13-18 dias de trabalho concentrado.

---

## Dependências Entre Fases

```
Fase 0 ✓ (Repositório SQLite extraído)
    ↓
Fase 1 (ORM + SQLAlchemy)
    ↓
Fase 2 (Migração de tabelas para ORM)
    ↓
Fase 3 (Refatoração de casos de uso)
    
Fase 4 (Hooks frontend) - independente
    ↓
Fase 5 (App shell simplificado)
    ↓
Fase 6 (Testes e validação)
```

---

## Arquitetura Alvo

### Backend (Camadas)

```
HTTP/WS Layer (main.py)
    ↓
Application (use_cases/)
    ↓
Domain (models.py, repository interfaces)
    ↓
Infrastructure (repositories/ + ORM)
```

### Frontend (Composição)

```
App Shell (roteamento + shell simples)
    ↓
Page Containers (por tela)
    ↓
Hooks (discovery, session, library, workspace, export)
    ↓
Components (apresentação pura)
```

---

## Critério de Aceite por Fase

**Fase 0** ✓
- [ ] Repositório SQLite extraído em módulo próprio
- [ ] JobService aponta para repositório
- [ ] Smoke test de criar/listar/ler sessão passa

**Fase 1**
- [ ] SQLAlchemy 2.x + Alembic instalado
- [ ] Models ORM criados para sessions, mix_state, exports, events
- [ ] Engine e session factory configurados
- [ ] Primeira migração gerada a partir do schema atual

**Fase 2**
- [ ] SessionRepository reimplementado com ORM
- [ ] Testes de repositório (CRUD) passam
- [ ] API endpoints continuam retornando o mesmo JSON
- [ ] Nenhuma regressão em leitura/escrita de sessões

**Fase 3**
- [ ] CreateSessionUseCase, ProcessSessionUseCase, ExportSessionUseCase criados
- [ ] JobService delegava para casos de uso
- [ ] Endpoints continuam funcionando
- [ ] Fluxo de processamento validado

**Fase 4**
- [ ] useDiscovery, useSession, useLibrary, useWorkspace, useExport criados
- [ ] Lógica de App.jsx movida para hooks
- [ ] Nenhuma mudança visual esperada

**Fase 5**
- [ ] App.jsx reduzido a shell de navegação + provider
- [ ] Props de páginas simplificadas
- [ ] Funcionalidade inalterada

**Fase 6**
- [ ] Testes de contrato (backend) >= 80%
- [ ] Testes de fluxo UI >= 60%
- [ ] QA manual completa (desktop + mobile)
- [ ] Documentação de mudanças arquiteturais atualizada

---

## Próximas Ações

1. **Agora (Fase 1)**: Instalar e configurar SQLAlchemy 2.x + Alembic
2. **Depois (Fase 2)**: Migrar tabelas de uma em uma
3. **Depois (Fase 3)**: Refatorar serviço em casos de uso
4. **Em paralelo (Fases 4-5)**: Extrair hooks e simplificar App
5. **Final (Fase 6)**: Validar e consolidar

---

## Documentação de Suporte

- `PHASE_1_ORM_SETUP.md`: Configuração de SQLAlchemy + Alembic
- `PHASE_2_ORM_MIGRATION.md`: Migração tabela por tabela
- `PHASE_3_USE_CASES.md`: Refatoração de JobService
- `PHASE_4_FRONTEND_HOOKS.md`: Extração de hooks
- `PHASE_5_FRONTEND_SHELL.md`: Simplificação de App.jsx
- `PHASE_6_TESTING.md`: Plano de testes consolidado

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|--------|-----------|
| Regressão em leitura/escrita | Média | Alto | Testes de contrato em cada migração |
| Falta de contexto do ORM | Alta | Médio | Documentação + exemplos inline |
| Perda de dados em migração | Baixa | Crítico | Backup + teste em cópia antes |
| Paralização em integração | Média | Médio | Integração diária + CI/CD |


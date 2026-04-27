# Backend Coverage Matrix For Front Proposal

## Objetivo
Definir o plano backend, em ordem de prioridade, para cobrir 100% do que esta proposto nas telas estaticas de Descobrir, Processamento, Workspace e Biblioteca.

## Status atual de cobertura

### Ja coberto
- Busca de fontes por termo ou URL.
- Criacao de processamento.
- Status de job por polling.
- Atualizacao em tempo real via WebSocket.
- Geracao de stems reais com Demucs.
- Download de stem por endpoint dedicado.
- Selecao de stems alvo no request de processamento.

### Parcial
- Sessao amigavel MX-xxx existe no frontend, mas nao e persistida no backend.
- Processamento possui mensagens de estado, mas nao possui historico estruturado de eventos.

### Nao coberto
- Biblioteca real (listar, filtrar, paginar, retomar, duplicar, reprocessar).
- Persistencia de sessoes (hoje e memoria volatil).
- Estado de mixer salvo por sessao.
- Export jobs (mix final, presets de exportacao, status de export).
- Metricas de master no backend (LUFS, true peak, headroom).
- Score de compatibilidade para candidatos na busca.

## Matriz priorizada de implementacao

## P0 - Biblioteca funcional e persistencia
Objetivo: habilitar o fluxo principal da Biblioteca (retomar, duplicar, acompanhar, reprocessar) com dados reais e persistentes.

### Entregas
1. Persistencia de sessoes
- Adotar armazenamento persistente (SQLite para MVP local, com caminho para PostgreSQL depois).
- Guardar sessoes, trilha selecionada, status, stems, timestamps e erros.

2. Session code backend
- Gerar e persistir codigo amigavel de sessao (MX-001, MX-002, ...).
- Retornar session_code em todas as respostas de sessao.

3. Endpoints de biblioteca
- GET /api/sessions
  - filtros: query, status, created_from, created_to
  - paginacao: page, page_size
  - ordenacao: created_at desc default
- GET /api/sessions/{session_id}
- POST /api/sessions/{session_id}/duplicate
- POST /api/sessions/{session_id}/reprocess

4. Compatibilidade com fluxo atual
- Manter GET /api/jobs/{job_id} e WS /ws/{job_id} durante transicao.
- Mapear job_id para session_id internamente sem quebrar frontend atual.

### Modelos sugeridos
- SessionSummary
  - session_id, session_code, track_title, artist, status, created_at, updated_at
- SessionDetail
  - SessionSummary + selected_track + target_stems + stems + error + progress + message
- SessionListResponse
  - items, page, page_size, total

### Criterio de aceite
- Reiniciar backend nao apaga historico da Biblioteca.
- Biblioteca lista sessoes reais com filtros e paginacao.
- Duplicar cria nova sessao queued com a mesma configuracao.
- Reprocessar cria nova execucao para a sessao alvo.

## P1 - Workspace com estado salvo e export real
Objetivo: conectar controles de Workspace com backend para retomar e exportar com previsibilidade.

### Entregas
1. Persistir estado de mixer
- GET /api/sessions/{session_id}/mix-state
- PUT /api/sessions/{session_id}/mix-state
- Campos minimos: per_stem gain, pan, mute, solo, send_fx, master_gain, updated_at

2. Export jobs
- POST /api/sessions/{session_id}/exports
  - payload: preset (study_mix, stems, custom), format (wav, zip), options
- GET /api/sessions/{session_id}/exports/{export_id}
- GET /api/sessions/{session_id}/exports

3. Artefatos de export
- Mix final (arquivo unico) e pacote de stems.
- URL de download por artefato finalizado.

### Modelos sugeridos
- MixState
- ExportJob
  - export_id, session_id, type, state, progress, output_files, error, created_at, updated_at

### Criterio de aceite
- Usuario sai e volta ao Workspace e encontra os mesmos faders e controles.
- Exportar mix e baixar stems funciona com status consultavel.
- Biblioteca exibe que a sessao possui export disponivel.

## P2 - Observabilidade e qualidade de decisao
Objetivo: suportar os elementos ricos da proposta de Processamento e Descobrir.

### Entregas
1. Event log estruturado
- GET /api/sessions/{session_id}/events
- Evento com timestamp, stage, level, message, progress

2. Compatibilidade na busca
- Incluir no SearchCandidate: compatibility_score (0-100) e opcional breakdown simplificado
- Ajustar recommended_source_id mantendo backward compatibility

3. Telemetria util
- ETA aproximado durante processing (best effort)
- device usado (cpu/cuda) na resposta de sessao

### Criterio de aceite
- Tela de Processamento renderiza log de eventos reais com horario.
- Tela de Descobrir exibe compatibilidade baseada em dado real de backend.

## Modelo de dados minimo (MVP)
- sessions
  - id (uuid pk), session_code (unique), query, selected_source_json, target_stems_json
  - state, progress, message, error, created_at, updated_at
- session_artifacts
  - id, session_id, kind (stem, mix, zip), stem_name nullable, path, size_bytes, created_at
- session_mix_state
  - session_id pk, payload_json, updated_at
- session_events
  - id, session_id, ts, stage, level, progress, message
- export_jobs
  - id, session_id, type, state, progress, error, output_json, created_at, updated_at

## Sequencia recomendada de entrega
1. P0.1 Persistencia + session_code + GET /api/sessions
2. P0.2 duplicate e reprocess
3. P1.1 mix-state save/load
4. P1.2 export jobs e downloads
5. P2.1 events e compatibilidade da busca

## Riscos e mitigacoes
- Risco: quebrar frontend atual durante migracao
  - Mitigacao: manter endpoints atuais e adicionar novos em paralelo.
- Risco: custo de processamento para reprocess em lote
  - Mitigacao: fila simples com limite de concorrencia por ambiente.
- Risco: lock de arquivo local em SQLite sob carga
  - Mitigacao: WAL mode, e caminho claro para PostgreSQL.

## Definition of done final (100% proposta)
- Biblioteca real com dados persistentes, filtro, retomar, duplicar, reprocessar.
- Processamento com eventos reais e estados consistentes.
- Workspace com estado salvo e export funcional.
- Descobrir com score de compatibilidade vindo do backend.

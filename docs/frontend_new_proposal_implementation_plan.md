# Plano de Implementacao Frontend - Nova Proposta

## Objetivo
Implementar no frontend React a proposta visual e funcional de Descobrir, Processamento, Workspace e Biblioteca, conectando totalmente com os endpoints backend ja prontos.

## Base atual confirmada
- O frontend atual ja possui estrutura de paginas em um unico App e client API com chamadas para sessoes, eventos, mix-state e exports.
- O backend ja expõe endpoints para:
  - busca e processamento
  - sessoes com filtro e paginacao
  - eventos de sessao
  - mix-state
  - exports e download de arquivos
- Falta integrar esses endpoints na interface real de forma consistente e com estado robusto.

## Principios de execucao
1. Entregar valor por fatias verticais de tela para reduzir retrabalho.
2. Migrar sem quebrar fluxo atual de criar sessao e acompanhar progresso.
3. Primeiro conectar dados reais, depois refinar UX e performance.
4. Salvar estado de mixer com debounce para evitar excesso de requests.
5. Fechar com testes de fluxo ponta a ponta do journey completo.

## Status de execucao atual (2026-04-18)

### Concluido
1. Fase 1 finalizada: modularizacao por paginas e session context em producao.
2. Fase 2 finalizada: Biblioteca conectada com filtros, paginacao, abrir, duplicar e reprocessar.
3. Fase 3 finalizada: Processamento com hydrate de sessao, eventos reais, ETA e separation_device.
4. Fase 4 finalizada: Workspace com load/save de mix-state (debounce + diff) e master_metrics.
5. Fase 5 finalizada: Exportacao real com create/list/poll/retry/download por sessao.
6. Fase 6 finalizada: Descobrir com compatibility_score e compatibility_breakdown do backend.

### Validacao tecnica recente
1. Build frontend em producao executado com sucesso (`npm run build`).
2. Sem erros no editor para `frontend/src` apos as ultimas alteracoes.
3. Verificacao de disponibilidade local por script indica backend/frontend fora do ar no momento, entao a validacao funcional fim-a-fim depende de subir os servicos.
4. Smoke test local de backend via JobService validou fluxo minimo de sessao, persistencia de mix-state e export (`export_state=ready`).

### Fase 7 executada (QA final)
1. Servicos locais iniciados com sucesso:
- backend em `http://localhost:8000`
- frontend em `http://localhost:5173`
2. Checklist funcional validado por API:
- Descobrir: `/api/search` retornando candidatos com `compatibility_score` e `compatibility_breakdown`.
- Processamento: `/api/sessions/{id}` e `/events` retornando estado e historico de eventos.
- Workspace: `GET/PUT /mix-state` validado com persistencia de ajuste de master_gain.
- Export: `POST/GET /exports` validado com estado `ready` e arquivo de download disponivel.
3. Checklist de UI validado no frontend local:
- Descobrir carregando resultados reais e score de compatibilidade.
- Biblioteca listando sessoes reais com acoes por linha.
- Workspace abrindo sessao da biblioteca e criando export com sucesso.
- Processamento exibindo telemetria e log de eventos reais.
4. Correcao aplicada durante QA:
- Endpoint de stems recebeu suporte explicito a HEAD em `backend/app/main.py`, eliminando erro 405 observado no browser ao ler tamanho dos stems.

### Pendencia residual
1. Confirmar responsividade manual completa em viewport mobile dedicado (layout estrutural esta responsivo, mas falta checklist visual formal de aceite mobile).

## Roadmap por fase

## Fase 1 - Estrutura e fundacao do front
Duracao sugerida: 1 a 2 dias.

### Entregas
1. Separar App monolitico em modulos por pagina:
- pages/DiscoverPage
- pages/SessionPage
- pages/WorkspacePage
- pages/LibraryPage

2. Criar camada de estado compartilhado de sessao atual:
- session context simples com session_id, session_code, job_id e status
- sincronizacao entre telas sem duplicar fetches

3. Padronizar tratamento de erro e loading:
- estados vazios, erro de rede, retries manuais

### Critério de aceite
- Sem mudanca visual relevante.
- Navegacao entre paginas funcionando igual ao estado atual.
- Nenhuma regressao no fluxo buscar e iniciar processamento.

## Fase 2 - Biblioteca real conectada
Duracao sugerida: 2 dias.

### Entregas
1. Integrar listagem real usando listSessions.
2. Implementar filtros reais:
- query
- status
- created_from e created_to
3. Implementar paginacao da tabela.
4. Integrar ações:
- duplicar sessao
- reprocessar sessao
- abrir workspace de sessao selecionada
- acompanhar sessao em processamento

### Critério de aceite
- Biblioteca exibe dados reais persistidos do backend.
- Filtros e paginacao alteram resultados sem reload de pagina.
- Duplicar e reprocessar disparam novos processamentos com retorno de session_code.

## Fase 3 - Processamento com dados reais de observabilidade
Duracao sugerida: 1 a 2 dias.

### Entregas
1. Continuar usando WebSocket para progresso em tempo real.
2. Integrar getSession para hydrate de pagina quando abrir por URL/sessao existente.
3. Integrar getSessionEvents para log real da sessao.
4. Exibir ETA e separation_device quando disponíveis.

### Critério de aceite
- Pagina de Processamento funciona para sessao nova e sessao aberta da Biblioteca.
- Log de eventos e metadados do backend aparecem corretamente.

## Fase 4 - Workspace funcional com persistencia de mix
Duracao sugerida: 2 a 3 dias.

### Entregas
1. Carregar mix-state real ao abrir Workspace.
2. Salvar mix-state com debounce ao alterar faders e controles.
3. Refletir master_metrics da sessao quando disponíveis.
4. Bloquear ações de export quando sessao nao estiver pronta.

### Critério de aceite
- Ajustes de mix persistem ao sair e voltar da tela.
- Sessao carregada da Biblioteca abre com estado correto de controles.

## Fase 5 - Exportacao real
Duracao sugerida: 2 dias.

### Entregas
1. Integrar criacao de export job:
- preset study_mix
- preset stems
- preset custom com opcoes
2. Integrar listagem de export jobs por sessao.
3. Integrar consulta de status por export e UI de progresso.
4. Integrar download via getExportFileUrl.

### Critério de aceite
- Usuario cria export, acompanha status e baixa arquivo final pela interface.
- Erros de export aparecem com mensagem clara e ação de retry.

## Fase 6 - Refinamento de Descobrir e consistencia final
Duracao sugerida: 1 dia.

### Entregas
1. Mostrar compatibility_score e breakdown na lista de candidatos.
2. Alinhar textos e labels com a proposta estatica.
3. Revisar estados e chips para coerencia entre telas.

### Critério de aceite
- Descobrir usa score real do backend.
- Jornada visual completa consistente com a proposta.

## Backlog tecnico recomendado

## Bloco A - Arquitetura
1. Extrair componentes de layout compartilhado.
2. Criar hooks de dados por dominio:
- useSessionList
- useSessionDetail
- useSessionEvents
- useMixState
- useExports
3. Centralizar mapeamento de estados backend para labels e badges.

## Bloco B - Biblioteca
1. Tabela com paginação e filtros controlados.
2. Ações por linha com feedback visual de sucesso e erro.
3. Navegação para SessionPage e WorkspacePage mantendo session_id.

## Bloco C - Processamento
1. Rehidratação por getSession ao entrar na pagina.
2. Stream via websocket e fallback por polling eventual.
3. Timeline e log alimentados por session events.

## Bloco D - Workspace
1. Form state para mixer com persistencia incremental.
2. Painel de arquivos e stems usando dados reais da sessao.
3. Painel de export com criação, acompanhamento e download.

## Bloco E - Qualidade
1. Testes de integração para API client.
2. Testes de fluxo de usuario para jornada completa.
3. QA manual em desktop e mobile.

## Sequencia de deploy sugerida
1. Deploy 1:
- Fase 1 + Fase 2
2. Deploy 2:
- Fase 3 + Fase 4
3. Deploy 3:
- Fase 5 + Fase 6

## Riscos e mitigacoes
- Risco: App.jsx crescer sem controle novamente.
- Mitigacao: extrair pagina por pagina antes de integrar novos recursos.

- Risco: excesso de requests ao salvar mix-state.
- Mitigacao: debounce e save somente em diff.

- Risco: UX travar durante export.
- Mitigacao: estado assíncrono por job com polling leve e mensagens claras.

## Definition of Done frontend
1. Biblioteca operando com dados reais e ações completas.
2. Processamento com progresso realtime e eventos reais.
3. Workspace com mix-state persistente e export funcional.
4. Descobrir com compatibilidade real dos candidatos.
5. Fluxo completo validado em mobile e desktop.

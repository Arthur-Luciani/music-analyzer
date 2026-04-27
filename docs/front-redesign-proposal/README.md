# Front Redesign Proposal (Static)

## Objetivo
Apresentar uma proposta de front mais madura, com fluxo completo e linguagem de produto para um app de separacao de stems.

## Referencias analisadas
- Moises: onboarding direto para acao, confianca de marca e UX orientada a musicos.
- LALAL.AI: funil simples (selecionar, enviar, processar), estados claros e operacao em fila.
- Ableton Live: hierarquia de informacao focada em workflow, feedback rapido e ambiente de trabalho musical.

## Principios aplicados
1. Sem UUID na interface do usuario.
2. Identificador amigavel de sessao (exemplo: MX-024).
3. Hierarquia clara por tela (descobrir, processar, trabalhar, revisar historico).
4. Feedback continuo de estado (chips, timeline, progresso, log).
5. Controles de audio com mentalidade de mixer simplificado.
6. Design system consistente (tipografia, cores, botoes, cards, status).

## Estrutura das paginas
- index.html: descoberta e selecao de fonte.
- session.html: acompanhamento de processamento em tempo real.
- analysis-preview.html: conceito estatico detalhado da pre-visualizacao da analise durante separacao.
- workspace.html: mixer e exportacao de stems.
- library.html: historico de sessoes e retomada.

## Jornada simplificada
1. Descobrir: escolher uma unica fonte e seguir.
2. Processamento: apenas monitorar progresso ate finalizar.
3. Workspace: ouvir, mixar e exportar no mesmo lugar.
4. Biblioteca: retomar sessoes prontas ou duplicar.

## Observacoes de produto
- UUID deve existir apenas no backend para rastreabilidade tecnica.
- Front deve expor nome da sessao + codigo curto para comunicacao com usuario/suporte.
- Em producao, esses layouts podem ser migrados para React com os mesmos componentes visuais.

# Plano de Implementacao da Proxima Etapa - Pipeline Real com Demucs

## Objetivo
Implementar a proxima etapa do MVP: separar stems reais (vocals, drums, bass, other) a partir do audio ja baixado com yt-dlp, substituindo a parte mockada do estado `separating`.

## Estudo rapido do Demucs (uso correto)

Fontes oficiais consultadas:
- https://github.com/facebookresearch/demucs (README)
- https://pypi.org/project/demucs/

Pontos importantes de uso:
- Instalacao basica: `pip install -U demucs`.
- Modelo default no v4: `htdemucs`.
- Saida padrao: `separated/MODEL/TRACK_NAME/{vocals,drums,bass,other}.wav`.
- Suporte de device:
- GPU: usar `-d cuda`.
- CPU fallback: `-d cpu`.
- Flags relevantes para producao:
- `--segment` para controle de memoria.
- `--overlap` (default 0.25) para qualidade/velocidade.
- `--shifts` aumenta qualidade e custo computacional.
- `--two-stems=vocals` e opcao de karaoke; nao reduz custo (separacao completa ainda acontece).
- API Python suportada:
- `demucs.separate.main([...args...])`.
- Isso permite integrar no backend sem shell script externo.

Observacao de manutencao:
- O repositorio `facebookresearch/demucs` esta arquivado.
- Para evolucao futura, acompanhar fork do autor: https://github.com/adefossez/demucs.

## Escopo da implementacao

Entradas:
- Arquivo baixado em `storage/raw/{job_id}/source.*`.

Saidas esperadas:
- `storage/stems/{job_id}/vocals.wav`
- `storage/stems/{job_id}/drums.wav`
- `storage/stems/{job_id}/bass.wav`
- `storage/stems/{job_id}/other.wav`

Estados do job (WebSocket):
1. `downloading` (ja real)
2. `separating` (passa a ser real)
3. `ready` com paths reais
4. `failed` com erro tecnico detalhado

## Mudancas de codigo planejadas

### 1) Backend - pipeline real
Arquivo: `backend/app/services/jobs.py`

Implementar:
1. Funcao `_run_demucs(input_audio_path, job_id)`.
2. Chamada do Demucs via API Python:
   - `demucs.separate.main([...])`
   - Argumentos iniciais sugeridos:
   - `--name htdemucs`
   - `--device cuda` (com fallback para cpu)
   - `--out storage/stems/{job_id}` (temporario e depois normalizar estrutura)
3. Pos-processamento dos arquivos para padronizar caminho final em `storage/stems/{job_id}`.
4. Atualizacao dos eventos de progresso com mensagens reais.
5. Tratamento de excecoes com mensagem util para API/UI.

### 2) Backend - configuracao
Arquivo novo sugerido: `backend/app/settings.py` (ou equivalente)

Configurar por variavel de ambiente:
1. `SEPARATION_MODEL=htdemucs`
2. `SEPARATION_DEVICE=auto|cuda|cpu`
3. `SEPARATION_SEGMENT=7.8` (safe para HTDemucs)
4. `SEPARATION_OVERLAP=0.25`
5. `SEPARATION_SHIFTS=1`
6. `TORCH_HOME=/app/storage/cache/torch` (docker)

### 3) Documentacao
Arquivo: `README.md`

Atualizar:
1. Fluxo agora com separacao real.
2. Requisitos de memoria GPU e fallback CPU.
3. Variaveis de ambiente do pipeline.
4. Troubleshooting de falta de memoria CUDA.

## Avaliacao de impacto de infraestrutura

## Mudancas obrigatorias
1. `backend/Dockerfile` deve instalar tambem `backend/requirements.pipeline.txt`.
   - Hoje instala apenas `requirements.txt`.
   - Sem isso, Demucs/Torch nao estarao no container.

2. Garantir cache de modelos persistente em storage.
   - Definir `TORCH_HOME=/app/storage/cache/torch` no backend.
   - O volume `./storage:/app/storage` ja existe no compose (ponto positivo).

## Mudancas recomendadas
1. Adicionar fallback automatico para CPU quando CUDA indisponivel.
2. Definir timeout por job para evitar travamentos longos.
3. Limitar concorrencia de jobs (1 por GPU inicialmente).
4. Logging de etapa (download/preprocess/separate/finalize).

## Mudancas de compose (provavel)
Arquivo: `docker-compose.yml`

Adicionar no service `backend`:
1. `TORCH_HOME=/app/storage/cache/torch`
2. Variaveis `SEPARATION_*`
3. Opcional: perfil `cpu` e `gpu` para ambientes diferentes.

## Nota sobre ambiente local sem Docker
Para rodar Demucs localmente, alem de `requirements.txt`, sera necessario instalar:
- `pip install -r backend/requirements.txt -r backend/requirements.pipeline.txt`

Recomendacao de compatibilidade:
- Usar Python 3.10 ou 3.11 no backend local para reduzir risco de incompatibilidade de wheels de GPU.

## Plano de testes (aceitacao)

Teste 1 - Separacao feliz (GPU):
1. Buscar faixa.
2. Selecionar fonte.
3. Iniciar job.
4. Confirmar criacao de 4 stems reais.
5. Confirmar `state=ready` com paths validos.

Teste 2 - Fallback CPU:
1. Forcar `SEPARATION_DEVICE=cpu`.
2. Executar job.
3. Confirmar sucesso com tempo maior.

Teste 3 - Erro de infraestrutura:
1. Simular erro do Demucs (modelo invalido).
2. Confirmar `state=failed` e mensagem clara para diagnostico.

Teste 4 - Persistencia cache:
1. Rodar 2 jobs iguais.
2. Confirmar que segunda execucao nao baixa modelo novamente (ou baixa menos).

## Roadmap de entrega da etapa

Fase A - Integracao funcional:
1. Implementar `_run_demucs` + wiring no `run_pipeline`.
2. Entregar stems reais e remover mock de separacao.

Fase B - Infra e operacao:
1. Ajustar Dockerfile e compose com pipeline deps e cache.
2. Configurar variaveis de ambiente.

Fase C - Hardening:
1. Fallback CPU, timeout e limite de concorrencia.
2. Atualizar README e checklist operacional.

## Decisao tecnica recomendada
Implementar Demucs via API Python (`demucs.separate.main`) dentro do backend, com configuracao por variavel de ambiente e fallback automatico para CPU. Isso reduz fragilidade de shell, melhora tratamento de erros e facilita observabilidade no WebSocket.

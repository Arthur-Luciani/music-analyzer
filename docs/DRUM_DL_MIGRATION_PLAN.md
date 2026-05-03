# Plano de Migração: Transcrição de Bateria via Deep Learning (Magenta/SOTA)

Este documento descreve o roteiro para substituir a arquitetura atual de análise de bateria por um modelo de Deep Learning no estado da arte (SOTA), resolvendo problemas de polifonia e classificação.

---

## FASE 1: Motor de Transcrição Isolado (Deep Learning)

Como o projeto usa **Python 3.13** e modelos de áudio geralmente exigem **Python 3.8 - 3.10**, usaremos uma arquitetura de isolamento.

### 1.1. Seleção do Modelo
*   **Prioridade:** Google Magenta (`onsets_and_frames` para bateria).
*   **Alternativa:** ADTLib ou modelos baseados em PyTorch (ex: modelos treinados no E-GMD).

### 1.2. Ambiente de Execução
*   Criar um `Dockerfile` ou ambiente Conda isolado para o "Worker" de bateria.
*   O backend principal chamará este worker via `subprocess` ou API interna.
*   **Entrada:** `drums.wav` (separado pelo Demucs).
*   **Saída:** Arquivo MIDI com notas mapeadas (General MIDI).

---

## FASE 2: Integração no Backend

### 2.1. Limpeza do Legado
*   Remover a extração de onsets manual via Librosa.
*   Descartar a lógica de treinamento próprio que estava sendo planejada.

### 2.2. Fluxo de Trabalho (Pipeline)
1.  **Demucs:** Isola a trilha de bateria.
2.  **DL-Worker:** Processa o áudio e gera um MIDI polifônico.
3.  **Parser:** O backend lê o MIDI e converte para nossa estrutura `DrumHit` (Kick, Snare, Hi-hat, etc.).

---

## FASE 3: Adaptação do Frontend

### 3.1. Suporte a Polifonia
*   Ajustar `DrumLanes.jsx` para lidar com múltiplos eventos no mesmo timestamp (ex: Bumbo + Hi-hat).
*   Garantir que a visualização não sobreponha os elementos de forma ilegível.

### 3.2. Exportação
*   Garantir que o export de MIDI e MusicXML reflita a polifonia capturada pelo novo modelo.

---

## Próximos Passos
1. Definir o modelo específico (Magenta vs outros).
2. Criar o container de execução isolado.

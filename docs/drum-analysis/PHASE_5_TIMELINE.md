# Fase 5 — Timeline Visual Sincronizada

**Duração**: 4–6 dias
**Objetivo**: Integrar uma visualização interativa do áudio da bateria, sincronizada com a reprodução
**Saída**: Waveform interativa com grid de batidas e marcadores coloridos por tipo de golpe

---

## Contexto

Para o usuário, ouvir a música e ver apenas métricas textuais (BPM, número de golpes) não é suficiente. A Fase 5 adiciona um componente visual rico: uma "waveform" (forma de onda) focada apenas no canal de bateria, sincronizada em tempo real com a reprodução de áudio.

Usaremos o **WaveSurfer.js** (v7) por ser leve, flexível e focar especificamente na renderização de formas de onda e marcadores (regions/markers).

---

## Estrutura Alvo no Frontend

```
frontend/src/
├── hooks/
│   └── useDrumTimeline.js        ← Gerencia o estado e sincronização do WaveSurfer
└── components/
    └── DrumTimeline.jsx          ← Componente React que renderiza a timeline
```

---

## Dependências

Adicionar ao `frontend/package.json`:

```bash
npm install wavesurfer.js@^7
```

Opcional: `wavesurfer.js/dist/plugins/regions.esm.js` ou `timeline.esm.js` se formos usar plugins nativos para marcadores, ou podemos desenhar nativamente no canvas.

---

## Componente de Timeline

O componente `DrumTimeline` fará:
1. Renderizar a forma de onda do áudio (usando o arquivo MP3/WAV do stem de bateria gerado pelo Demucs).
2. Desenhar linhas verticais para cada `beat` retornado pela API na Fase 1.
3. Desenhar marcadores (com cores ou ícones) para cada `hit` retornado pela Fase 3.
4. Manter o cursor de reprodução sincronizado com o tempo global do `useWebAudioMixer`.

### Cores Sugeridas para os Hits

```javascript
const HIT_COLORS = {
  kick: '#ff4d4f',    // Vermelho
  snare: '#1890ff',   // Azul
  hihat: '#52c41a',   // Verde
  tom: '#faad14',     // Amarelo
  cymbal: '#722ed1',  // Roxo
  unknown: '#8c8c8c'  // Cinza
};
```

---

## Sincronização de Áudio

O grande desafio desta fase é garantir que a timeline do WaveSurfer ande perfeitamente alinhada com o áudio reproduzido pelo sistema principal (`useWebAudioMixer.js`).

**Estratégia de Sincronização:**
Não deixaremos o WaveSurfer gerenciar a reprodução do áudio (ele ficaria fora de sincronia com os outros stems). Em vez disso:
- O sistema principal (`useWebAudioMixer`) continua sendo o "Master Clock" via Web Audio API.
- O componente de timeline escuta as mudanças de `currentTime` do player principal e atualiza a posição do cursor do WaveSurfer programaticamente (`wavesurfer.seekTo()`).
- Cliques na timeline do WaveSurfer disparam a função de "seek" (pular para posição) do player principal.

---

## Implementação Conceitual do Hook

**`frontend/src/hooks/useDrumTimeline.js`**

```javascript
import { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js';

export function useDrumTimeline(containerRef, audioUrl, drumAnalysis, currentTime, onSeek) {
  const wavesurfer = useRef(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !audioUrl) return;

    wavesurfer.current = WaveSurfer.create({
      container: containerRef.current,
      url: audioUrl,
      waveColor: '#4b5563',
      progressColor: '#3b82f6',
      cursorColor: '#ef4444',
      height: 120,
      interact: true, // Permitir clique para pular
      plugins: [
        TimelinePlugin.create(),
        RegionsPlugin.create()
      ],
    });

    wavesurfer.current.on('ready', () => {
      setIsReady(true);
      // Aqui vamos desenhar os marcadores baseados no drumAnalysis
      if (drumAnalysis) {
        drawMarkers(wavesurfer.current, drumAnalysis);
      }
    });

    wavesurfer.current.on('click', (relativeX) => {
      // Se o usuário clicar na onda, repassa para o player mestre
      if (onSeek) {
        const time = relativeX * wavesurfer.current.getDuration();
        onSeek(time);
      }
    });

    return () => {
      wavesurfer.current.destroy();
    };
  }, [audioUrl, containerRef]);

  // Atualizar cursor quando o áudio toca
  useEffect(() => {
    if (isReady && wavesurfer.current && !wavesurfer.current.isPlaying()) {
       // Apenas atualiza a posição visual se não estiver tocando nativamente no wavesurfer
       const duration = wavesurfer.current.getDuration();
       if (duration > 0) {
         wavesurfer.current.seekTo(currentTime / duration);
       }
    }
  }, [currentTime, isReady]);

  return { wavesurfer: wavesurfer.current, isReady };
}

function drawMarkers(ws, analysis) {
  const regions = ws.getActivePlugins()[1]; // RegionsPlugin
  
  // Desenhar beats (linhas transparentes)
  analysis.beats.forEach((time) => {
    regions.addRegion({
      start: time,
      end: time + 0.01,
      color: 'rgba(255, 255, 255, 0.1)',
      drag: false,
      resize: false
    });
  });

  // Desenhar hits
  analysis.hits.forEach((hit) => {
    const color = HIT_COLORS[hit.type] || HIT_COLORS.unknown;
    regions.addRegion({
      start: hit.time,
      end: hit.time + 0.05, // Largura fixa ou proporcional ao velocity
      color: color,
      drag: false,
      resize: false,
      content: hit.type === 'unknown' ? '' : hit.type[0].toUpperCase() // Primeira letra
    });
  });
}
```

---

## Inserindo no Workspace

No `WorkspacePage.jsx`, criamos um novo painel ou aba "Análise de Bateria" abaixo do player/mixer. 

Se a análise já existir (`drumAnalysis` carregado da API), mostramos o componente `DrumTimeline` e passamos a ele:
- O URL do stem de bateria (ex: `/api/sessions/{id}/stems/drums.mp3`)
- Os dados do `drumAnalysis`
- O `currentTime` atual do player mestre
- Uma função para o `onSeek`

---

## Checklist da Fase 5

- [ ] Instalar pacote `wavesurfer.js`
- [ ] Criar arquivo `frontend/src/hooks/useDrumTimeline.js`
- [ ] Criar componente `frontend/src/components/DrumTimeline.jsx`
- [ ] Waveform renderiza com sucesso o áudio do stem de bateria
- [ ] Sincronização do cursor funcionando (player mestre -> waveform)
- [ ] Clique na waveform atualiza o tempo no player mestre
- [ ] Beats renderizados como guias verticais
- [ ] Hits renderizados com cores específicas baseadas no `type`
- [ ] Degradê ou estilo visual responsivo (adapta-se à tela)
- [ ] Performance OK em músicas maiores (3-5 min) (pode exigir lazy rendering ou não criar milhares de "regions" DOM simultaneamente)

---

## Próxima Fase

A **Fase 6** fecha o projeto transformando os mesmos dados (que geraram MIDI/MusicXML na Fase 4) em uma partitura musical tradicional renderizada diretamente no navegador.

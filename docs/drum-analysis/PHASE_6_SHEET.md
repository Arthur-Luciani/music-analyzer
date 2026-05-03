# Fase 6 — Partitura de Bateria Renderizada no Browser

**Duração**: 4–5 dias
**Objetivo**: Exibir a transcrição da bateria como partitura musical tradicional (staves, notes, rests) diretamente na interface, sincronizada com o áudio.
**Saída**: Componente React `<DrumSheet />` integrado ao Workspace.

---

## Contexto

Embora os usuários possam baixar o MusicXML (Fase 4) e abrir no MuseScore, a experiência ideal é permitir que vejam a notação musical "in-app", enquanto escutam a música. 

Bateristas frequentemente querem ler a partitura enquanto tocam junto com a faixa. Para isso, precisamos pegar os dados de `beats` e `hits` (quantizados) e desenhá-los em um canvas/SVG usando as regras complexas de notação musical.

Utilizaremos a biblioteca **VexFlow**, que é o padrão da indústria para renderização de partituras no browser.

---

## Estrutura Alvo no Frontend

```
frontend/src/
├── components/
│   └── DrumSheet/
│       ├── DrumSheet.jsx          ← Componente React
│       ├── VexFlowRenderer.js     ← Lógica pura de renderização VexFlow
│       └── utils.js               ← Conversão de JSON de análise para VexFlow StaveNotes
```

---

## Dependências

Adicionar ao `frontend/package.json`:

```bash
npm install vexflow@^4
```

---

## Notação de Bateria Padrão

A notação de bateria usa cabeças de notas (noteheads) diferentes para peças diferentes e as posiciona em linhas específicas do pentagrama (stave) com uma clave de percussão (duas linhas verticais grossas).

**Padrão simplificado a ser implementado:**

| Peça | Posição no Stave | Notehead |
|---|---|---|
| Kick (Bumbo) | Linha 1 (fundo) | Normal (bola oval) |
| Snare (Caixa) | Espaço 3 | Normal (bola oval) |
| Tom (qualquer) | Linha 4 | Normal (bola oval) |
| Hi-Hat (Fechado) | Acima do stave (x) | Cruz (x) |
| Cymbal (Crash) | Linha auxiliar acima | Losango/Diamante |

---

## O Desafio da Quantização Visual

Para desenhar uma partitura, não basta saber o timestamp de um golpe. Precisamos saber:
1. Em qual compasso (measure) ele está.
2. Em qual posição exata do compasso (ex: tempo 1, contra-tempo do 2, etc).
3. A duração da nota para preencher as lacunas com pausas (rests).

### 1. Conversão de Tempo para Ritmo

O backend (Fase 4) já expõe um método de quantização. O ideal é que o frontend faça uma chamada à API ou utilize o resultado pré-processado pela API:

O frontend precisará agrupar os hits por compasso (assumindo 4/4 na Fase 1, cada compasso tem 4 beats).

```javascript
// Exemplo conceitual do utils.js
function groupHitsByMeasure(hits, beats, timeSignature = "4/4") {
  // 1. Agrupar os beats em compassos (ex: a cada 4 beats = 1 compasso)
  // 2. Iterar pelos hits e colocar cada um no compasso correspondente baseado no timestamp
  // 3. Converter a posição do timestamp para uma fração rítmica (quarter note, oitava, semi-colcheia)
  return measures;
}
```

### 2. Lógica de Renderização (VexFlow)

**`frontend/src/components/DrumSheet/VexFlowRenderer.js`**

```javascript
import { Factory } from 'vexflow';

export function renderDrumSheet(containerId, measuresData, currentMeasureIndex) {
  const vf = new Factory({ renderer: { elementId: containerId, width: 800, height: 200 } });
  const score = vf.EasyScore();
  const system = vf.System();

  // Limpar container anterior
  document.getElementById(containerId).innerHTML = '';

  // Renderizar o compasso atual
  const measure = measuresData[currentMeasureIndex];
  
  if (!measure) return;

  // Clave de percussão
  const stave = vf.Stave({ y: 40 }).addClef('percussion').addTimeSignature('4/4');
  
  // Array de notas VexFlow (StaveNotes) baseadas no `measure.hits`
  // Mapeamento: 
  // Kick = { keys: ['f/4'], duration: 'q' } // exemplo simplificado
  // Snare = { keys: ['c/5'], duration: 'q' }
  // HiHat = { keys: ['g/5'], duration: 'q' } (com modificador style 'x')

  const notes = convertHitsToVexNotes(vf, measure.hits);
  
  // Preencher compasso com pausas (rests) se necessário para completar o 4/4
  // ...

  const voice = score.voice(notes, { time: '4/4' });
  vf.Formatter().joinVoices([voice]).formatToStave([voice], stave);

  stave.setContext(vf.getContext()).draw();
  voice.draw(vf.getContext(), stave);
}
```

---

## Integração de Sincronia (Follow Playback)

Igual à Timeline (Fase 5), a Partitura deve acompanhar a reprodução do áudio.

Como partituras ocupam muito espaço, uma abordagem viável para um componente embutido na página é exibir **apenas o compasso atual e o próximo** (estilo "karaokê" de partitura) ou exibir uma linha que rola horizontalmente.

```javascript
// DrumSheet.jsx (simplificado)
function DrumSheet({ drumAnalysis, currentTime }) {
  const [currentMeasure, setCurrentMeasure] = useState(0);

  useEffect(() => {
    // Calcular qual compasso estamos tocando agora baseado no currentTime
    const measureIndex = calculateMeasureFromTime(currentTime, drumAnalysis.beats);
    if (measureIndex !== currentMeasure) {
      setCurrentMeasure(measureIndex);
    }
  }, [currentTime]);

  useEffect(() => {
    // Redesenhar a partitura quando o compasso atual mudar
    renderDrumSheet('drum-sheet-container', parsedMeasures, currentMeasure);
  }, [currentMeasure]);

  return <div id="drum-sheet-container" className="drum-sheet"></div>;
}
```

---

## Desafios Esperados e Mitigações

| Desafio | Solução |
|---|---|
| **Polirritmia / Notas Complexas** | VexFlow requer subdivisões matemáticas perfeitas. Se o usuário tocar uma quiáltera maluca (ex: 5 contra 4), a lógica de quantização pode falhar. **Mitigação:** Arredondar estritamente para semicolcheias (16th notes) para visualização na tela. |
| **Pausas (Rests)** | O VexFlow exige que a voz some perfeitamente a 4/4. Um hit no tempo 1 e outro no tempo 3 requer a injeção manual de um "rest" no tempo 2. |
| **Múltiplos hits no mesmo tempo** | Kick + Hi-Hat ao mesmo tempo. **Mitigação:** VexFlow suporta múltiplas chaves (keys) num mesmo `StaveNote` (acordes). Ex: `{ keys: ['f/4', 'g/5'] }`. |

---

## Checklist da Fase 6

- [ ] Instalar pacote `vexflow`
- [ ] Criar estrutura de componentes `DrumSheet`
- [ ] Desenvolver função de agrupamento de hits por compasso (`groupHitsByMeasure`)
- [ ] Desenvolver função de quantização em 16th notes
- [ ] Mapear classes de instrumentos (kick, snare, etc) para as notas e noteheads correspondentes da pauta de bateria no VexFlow
- [ ] Renderizar um único compasso estático e validar se as notas desenham corretamente
- [ ] Lógica para injetar pausas (rests) automaticamente para completar a contagem do compasso
- [ ] Integrar com `currentTime` do player para atualizar qual compasso está sendo renderizado na tela (Sincronização Karaoke)
- [ ] Garantir responsividade do canvas SVG/HTML do VexFlow

---

## Conclusão do Plano

Com a entrega da **Fase 6**, o `music-analyzer` terá evoluído de uma ferramenta genérica de separação de stems para um software profissional e especializado para bateristas, combinando IA de detecção de onsets, geração de MIDI/Partitura, e visualização gráfica rica no navegador.

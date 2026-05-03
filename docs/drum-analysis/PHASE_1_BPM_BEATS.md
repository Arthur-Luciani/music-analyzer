# Fase 1 — BPM, Beat Tracking e API de Análise

**Duração**: 3–4 dias
**Objetivo**: Detectar BPM e posição de cada batida no stem de drums; expor resultado via API
**Saída**: Endpoint `/drum-analysis` retornando BPM, beats e duração; BPM visível no workspace

---

## Contexto

Esta é a fase fundação. Com o stem de drums isolado pelo Demucs, usamos o `librosa` — já instalado — para extrair duas informações essenciais:

1. **BPM** — velocidade da música em batidas por minuto
2. **Beats** — lista de timestamps (em segundos) de cada batida

Esses dados alimentam todas as fases seguintes: a detecção de golpes (Fase 2) usa os beats como referência de grid, e a timeline visual (Fase 5) exibe os beats como linhas verticais na waveform.

A análise é **disparada pelo usuário** (botão no workspace), não automaticamente no pipeline de separação.

---

## Estrutura Alvo

```
backend/app/
├── models/
│   └── drum_analysis.py          ← DrumAnalysis, DrumHit (modelo Pydantic)
└── use_cases/
    └── analyze_drum_stem.py      ← AnalyzeDrumStemUseCase
```

### Novo endpoint em `main.py`

```
POST /api/sessions/{session_id}/drum-analysis   → dispara análise em background
GET  /api/sessions/{session_id}/drum-analysis   → retorna resultado salvo
```

---

## Modelo de Domínio

### `app/models/drum_analysis.py`

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DrumHit(BaseModel):
    """Representa um golpe individual de bateria."""
    time: float               # segundos desde o início
    type: str                 # kick | snare | hihat | tom | cymbal
    velocity: float = Field(ge=0.0, le=1.0)  # intensidade do golpe


class DrumAnalysis(BaseModel):
    """Resultado completo da análise do stem de bateria."""
    bpm: float                         # BPM global estimado
    time_signature: str = "4/4"        # compasso estimado
    duration_seconds: float            # duração total
    beat_count: int                    # total de beats detectados
    beats: list[float]                 # timestamps de cada beat [0.0, 0.5, 1.0, ...]
    hits: list[DrumHit] = []           # golpes detectados (populado na Fase 3)
    analysis_version: str = "1.0"
    analyzed_at: datetime
    status: str = "partial"            # partial | complete
```

---

## Caso de Uso

### `app/use_cases/analyze_drum_stem.py`

```python
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models.drum_analysis import DrumAnalysis
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AnalyzeDrumStemUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[DrumAnalysis]:
        job = await self._job_service.get_job(session_id)
        if job is None or not job.stems or "drums" not in job.stems:
            return None

        drum_stem_path = Path(job.stems["drums"])
        if not drum_stem_path.is_file():
            return None

        analysis = await asyncio.to_thread(
            self._run_analysis, drum_stem_path, session_id
        )
        self._persist_analysis(session_id, analysis)
        return analysis

    @staticmethod
    def _run_analysis(stem_path: Path, session_id: str) -> DrumAnalysis:
        import librosa
        import numpy as np

        # Carregar o stem de bateria
        # sr=22050 é suficiente para análise rítmica e mais rápido que 44100
        y, sr = librosa.load(str(stem_path), sr=22050)

        # Estimar BPM e detectar posição dos beats
        # O librosa usa um algoritmo de Dynamic Programming para beat tracking
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        # Estimar compasso a partir do número médio de beats por segmento
        # (estimativa simples, pode ser refinada na Fase 3)
        time_signature = _estimate_time_signature(beat_times)

        return DrumAnalysis(
            bpm=round(float(tempo), 1),
            time_signature=time_signature,
            duration_seconds=round(float(librosa.get_duration(y=y, sr=sr)), 2),
            beat_count=len(beat_times),
            beats=beat_times,
            analyzed_at=datetime.utcnow(),
            status="partial",  # hits serão adicionados na Fase 3
        )

    @staticmethod
    def _persist_analysis(session_id: str, analysis: DrumAnalysis) -> None:
        """Salva resultado em JSON junto à sessão para evitar reprocessamento."""
        output_path = settings.stems_root / session_id / "drum_analysis.json"
        output_path.write_text(analysis.model_dump_json(indent=2))

    @staticmethod
    def load_saved_analysis(session_id: str) -> Optional[DrumAnalysis]:
        """Carrega análise salva anteriormente, se existir."""
        path = settings.stems_root / session_id / "drum_analysis.json"
        if not path.is_file():
            return None
        try:
            return DrumAnalysis.model_validate_json(path.read_text())
        except Exception:
            return None


def _estimate_time_signature(beat_times: list[float]) -> str:
    """Estima compasso pelo agrupamento natural dos beats."""
    if len(beat_times) < 8:
        return "4/4"
    # Implementação simplificada na Fase 1 — sempre retorna 4/4
    # A Fase 3 pode refinar usando downbeat detection
    return "4/4"
```

---

## Integração no JobService

Adicionar ao `JobService.__init__`:

```python
from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase

self._analyze_drum_use_case = AnalyzeDrumStemUseCase(self)
```

Adicionar métodos:

```python
async def analyze_drum_stem(self, session_id: str) -> Optional[DrumAnalysis]:
    return await self._analyze_drum_use_case.execute(session_id)

async def get_drum_analysis(self, session_id: str) -> Optional[DrumAnalysis]:
    return AnalyzeDrumStemUseCase.load_saved_analysis(session_id)
```

---

## Rotas em `main.py`

```python
@app.post("/api/sessions/{session_id}/drum-analysis")
async def trigger_drum_analysis(session_id: str):
    """Dispara análise do stem de bateria em background."""
    asyncio.create_task(job_service.analyze_drum_stem(session_id))
    return {"status": "started"}


@app.get("/api/sessions/{session_id}/drum-analysis")
async def get_drum_analysis(session_id: str):
    """Retorna análise salva ou 404 se ainda não foi executada."""
    analysis = await job_service.get_drum_analysis(session_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Drum analysis not found")
    return analysis
```

---

## Frontend — BPM no Workspace

Adicionar ao painel de métricas do `WorkspacePage.jsx`, ao lado de LUFS/Peak/Headroom:

```jsx
// No hook useWorkspace ou WorkspaceContainer:
const [drumAnalysis, setDrumAnalysis] = useState(null);
const [drumAnalysisLoading, setDrumAnalysisLoading] = useState(false);

async function triggerDrumAnalysis() {
  setDrumAnalysisLoading(true);
  await api.post(`/sessions/${sessionId}/drum-analysis`);
  // Poll até resultado estar disponível
  // ...
  setDrumAnalysisLoading(false);
}
```

```jsx
// No painel de métricas (ao lado de LUFS, True Peak, Headroom):
<div>
  <span>BPM</span>
  <strong className="mono">{drumAnalysis?.bpm ?? "--"}</strong>
</div>
<div>
  <span>Compasso</span>
  <strong className="mono">{drumAnalysis?.time_signature ?? "--"}</strong>
</div>
<div>
  <span>Beats</span>
  <strong className="mono">{drumAnalysis?.beat_count ?? "--"}</strong>
</div>
```

---

## Tempo Estimado de Análise

| Duração da música | Tempo de análise (CPU) |
|---|---|
| 3 min | ~4–8 segundos |
| 5 min | ~7–14 segundos |
| 10 min | ~15–30 segundos |

Com GPU, `librosa` não acelera diretamente (é CPU-bound), mas o carregamento e processamento são rápidos por usar `sr=22050`.

---

## Checklist da Fase 1

- [ ] `app/models/drum_analysis.py` criado com `DrumHit` e `DrumAnalysis`
- [ ] `app/use_cases/analyze_drum_stem.py` criado com `AnalyzeDrumStemUseCase`
- [ ] `AnalyzeDrumStemUseCase` registrado no `JobService`
- [ ] Rotas `POST` e `GET` `/drum-analysis` adicionadas ao `main.py`
- [ ] Análise persiste em `{stems_root}/{session_id}/drum_analysis.json`
- [ ] Frontend exibe BPM, compasso e beat_count no painel de métricas
- [ ] Botão "Analisar Bateria" no workspace dispara o endpoint
- [ ] Backend compila sem erros: `python -m compileall app`

---

## Próxima Fase

A **Fase 2** usa os `beat_times` retornados aqui como referência de grid para detectar e segmentar golpes individuais de bateria, construindo o dataset de treinamento.

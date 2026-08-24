import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useWebAudioMixer } from "../hooks/useWebAudioMixer";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import InstrumentLane from "../components/InstrumentLane";
import { formatTrackLabel } from "../utils/formatters";

function formatClock(secondsValue) {
  const safeValue = Number.isFinite(secondsValue) ? Math.max(0, Math.floor(secondsValue)) : 0;
  const minutes = Math.floor(safeValue / 60);
  const seconds = safeValue % 60;
  const ms = Math.floor((secondsValue % 1) * 1000);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}:${String(ms).padStart(3, "0")}`;
}

function formatStemLabel(stemName) {
  const normalized = String(stemName || "").trim().toLowerCase();
  if (normalized === "vocals") return "Vocais";
  if (normalized === "drums") return "Bateria";
  if (normalized === "bass") return "Baixo";
  if (normalized === "other") return "Outros";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export default function WorkspacePage({
  job,
  sessionCode,
  stemsList,
  getStemAudioUrl,
  mixLevels,
  updateMixLevel,
  panLevels,
  updatePanLevel,
  onResetMix,
  soloStem,
  mutedStems,
  toggleStemMute,
  toggleStemSolo,
  mixStateLoading,
  mixStateSaving,
  mixStateError,
  onCreateStudyMixExport,
  masterMetrics,
  onGoDiscover,
  onGoLibrary,
  onApplyPreset,
  drumAnalysis,
  onGoDrumInspector,
}) {
  const isReady = job?.state === "ready";
  const stemsToRender = stemsList;
  const audioElementsRef = useRef({});
  const rafRef = useRef(null);
  const [activeStem, setActiveStem] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoopEnabled, setIsLoopEnabled] = useState(false);
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [currentTimeSeconds, setCurrentTimeSeconds] = useState(0);

  const stemNames = useMemo(() => stemsToRender.map(([stemName]) => stemName), [stemsToRender]);
  const canUsePlayer = Boolean(isReady && stemNames.length > 0 && job?.job_id);
  const wavesurferInstancesRef = useRef([]);

  const registerWavesurfer = useCallback((ws) => {
    wavesurferInstancesRef.current.push(ws);
    return () => {
      wavesurferInstancesRef.current = wavesurferInstancesRef.current.filter(i => i !== ws);
    };
  }, []);
  const playheadRef = useRef(null);

  const { initAudioContext, meters } = useWebAudioMixer({
    stemNames,
    audioElementsRef,
    mixLevels,
    panLevels,
    mutedStems,
    soloStem,
    isPlaying,
  });

  // Helper para sincronizar tudo o que é visual de uma vez
  const syncVisuals = useCallback((time, duration) => {
    if (!Number.isFinite(duration) || duration <= 0) return;
    const percent = (time / duration) * 100;
    
    // 1. Move Playheads
    const playheads = document.querySelectorAll(".playhead");
    playheads.forEach(ph => { ph.style.left = `${percent}%`; });

    // 2. Move WaveSurfers
    wavesurferInstancesRef.current.forEach(ws => {
      if (ws) ws.setTime(time);
    });
  }, []);

  useEffect(() => {
    let rafId;
    let lastStateUpdate = 0;

    const sync = () => {
      const activeAudio = audioElementsRef.current[activeStem];
      if (activeAudio && isPlaying) {
        const time = activeAudio.currentTime;
        const duration = activeAudio.duration;
        
        // Atualização visual 60fps
        syncVisuals(time, duration);

        // Atualização React State ~10fps
        const now = performance.now();
        if (now - lastStateUpdate > 100) {
          setCurrentTimeSeconds(time);
          if (Number.isFinite(duration)) setDurationSeconds(duration);
          lastStateUpdate = now;
        }

        rafId = requestAnimationFrame(sync);
      }
    };

    if (isPlaying) {
      rafId = requestAnimationFrame(sync);
    } else {
      cancelAnimationFrame(rafId);
    }
    return () => cancelAnimationFrame(rafId);
  }, [isPlaying, activeStem, syncVisuals]);

  const handleGlobalSeek = (percent) => {
    const newTime = percent * (durationSeconds || 0);
    seek(newTime);
    syncVisuals(newTime, durationSeconds);
  };

  const handleTransportSeek = (newTime) => {
    const safeTime = Math.max(0, Math.min(newTime, durationSeconds || 1000));
    seek(safeTime);
    syncVisuals(safeTime, durationSeconds);
  };

  async function playAll() {
    if (!canUsePlayer) return;
    initAudioContext();
    const playables = stemNames.map((n) => audioElementsRef.current[n]).filter(Boolean);
    try {
      await Promise.all(playables.map((a) => a.play()));
      setIsPlaying(true);
    } catch (e) {
      console.error("Erro ao reproduzir:", e);
    }
  }

  function pauseAll() {
    stemNames.forEach((n) => audioElementsRef.current[n]?.pause());
    setIsPlaying(false);
  }

  function seek(seconds) {
    const nextTime = Math.max(0, Math.min(seconds, durationSeconds || 1000));
    stemNames.forEach((n) => {
      if (audioElementsRef.current[n]) audioElementsRef.current[n].currentTime = nextTime;
    });
    setCurrentTimeSeconds(nextTime);
  }

  // Espaço (play/pause) e setas (retroceder/avançar 1s, ou 5s com Shift —
  // mesmo salto dos botões -5s/+5s) — mesmo padrão do Inspetor de Bateria.
  useKeyboardShortcuts(
    [
      { code: "Space", handler: () => (isPlaying ? pauseAll() : playAll()) },
      { code: "ArrowRight", handler: (e) => handleTransportSeek(currentTimeSeconds + (e.shiftKey ? 5 : 1)) },
      { code: "ArrowLeft", handler: (e) => handleTransportSeek(currentTimeSeconds - (e.shiftKey ? 5 : 1)) },
    ],
    { enabled: canUsePlayer }
  );

  useEffect(() => {
    if (stemNames.length && !activeStem) setActiveStem(stemNames[0]);
  }, [stemNames, activeStem]);

  useEffect(() => {
    stemNames.forEach((n) => {
      const audio = audioElementsRef.current[n];
      if (audio) {
        audio.muted = (soloStem && soloStem !== n) || mutedStems[n];
        audio.loop = isLoopEnabled;
      }
    });
  }, [stemNames, soloStem, mutedStems, isLoopEnabled]);

  // Cálculo da posição do playhead
  const playheadPosition = useMemo(() => {
    if (!durationSeconds) return 0;
    return (currentTimeSeconds / durationSeconds) * 100;
  }, [currentTimeSeconds, durationSeconds]);

  const [activePreset, setActivePreset] = useState("padrão");

  const handleApplyPreset = (name, levels) => {
    setActivePreset(name);
    if (name === "padrão") {
      onResetMix();
    } else {
      onApplyPreset(levels);
    }
  };

  if (!job) {
    return (
      <div className="workspace-layout">
        <header className="topbar">
          <div className="brand" onClick={onGoLibrary}>
            <div className="brand-badge">MX</div>
            <div className="brand-title"><strong>ESTÚDIO</strong><span>Aguardando Sessão</span></div>
          </div>
        </header>
        <main className="center-stage">
          <section className="card empty-state" style={{ textAlign: 'center', padding: '60px' }}>
            <h2>Nenhuma sessão carregada</h2>
            <p>Selecione um arquivo na sua biblioteca para começar a análise.</p>
            <button className="btn btn-primary" onClick={onGoDiscover}>Ir para Descobrir</button>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="workspace-layout">
      {/* 2. Control Dashboard */}
      <section className="control-dashboard">
        <div className="dashboard-group">
          <button className="btn-transport" onClick={() => handleTransportSeek(0)}>|&lt;</button>
          <button className="btn-transport" onClick={() => handleTransportSeek(currentTimeSeconds - 5)}>-5s</button>
          <button 
            className="btn-transport play" 
            onClick={isPlaying ? pauseAll : playAll}
          >
            {isPlaying ? "PAUSAR" : "REPRODUZIR"}
          </button>
          <button className="btn-transport" onClick={() => handleTransportSeek(currentTimeSeconds + 5)}>+5s</button>
          <button 
            className={`btn-transport ${isLoopEnabled ? "active" : ""}`}
            onClick={() => setIsLoopEnabled(!isLoopEnabled)}
            style={{ color: isLoopEnabled ? "var(--accent)" : "inherit" }}
          >
            REPETIR
          </button>
        </div>

        <div className="time-display-pro">{formatClock(currentTimeSeconds)}</div>

        <div className="dashboard-divider"></div>

        <div className="dashboard-group">
          <span style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 700, marginRight: 8 }}>PREDEFINIÇÕES:</span>
          <button 
            className={`pill-btn ${activePreset === "padrão" ? "active" : ""}`} 
            onClick={() => handleApplyPreset("padrão")}
          >
            PADRÃO
          </button>
          <button 
            className={`pill-btn ${activePreset === "vocal" ? "active" : ""}`} 
            onClick={() => handleApplyPreset("vocal", { vocals: 100, drums: 35, bass: 35, other: 35 })}
          >
            VOCAL
          </button>
          <button 
            className={`pill-btn ${activePreset === "bateria" ? "active" : ""}`} 
            onClick={() => handleApplyPreset("bateria", { vocals: 35, drums: 100, bass: 40, other: 30 })}
          >
            BATERIA
          </button>
          <button 
            className={`pill-btn ${activePreset === "karaokê" ? "active" : ""}`} 
            onClick={() => handleApplyPreset("karaokê", { vocals: 0, drums: 80, bass: 80, other: 80 })}
          >
            KARAOKÊ
          </button>
        </div>
      </section>

      {/* 3. Área de Trilhas */}
      <main className="lane-scroll-area">
        <div id="lane-stack">
          {stemsToRender.map(([stemName]) => (
            <InstrumentLane
              key={stemName}
              stemName={stemName}
              label={formatStemLabel(stemName)}
              audioUrl={getStemAudioUrl(job.job_id, stemName)}
              volume={mixLevels[stemName] ?? 60}
              isMuted={mutedStems[stemName]}
              isSolo={soloStem === stemName}
              onVolumeChange={(val) => updateMixLevel(stemName, val)}
              onMuteToggle={() => toggleStemMute(stemName)}
              onSoloToggle={() => toggleStemSolo(stemName)}
              onInspectorClick={stemName === "drums" ? onGoDrumInspector : null}
              isPlaying={isPlaying}
              accentColor="var(--accent)"
              onSeek={handleGlobalSeek}
              onRegister={registerWavesurfer}
            />
          ))}

          {/* Hidden Audios for useWebAudioMixer */}
          {stemsToRender.map(([stemName]) => (
            <audio
              key={`audio-${stemName}`}
              ref={(node) => (audioElementsRef.current[stemName] = node)}
              src={getStemAudioUrl(job.job_id, stemName)}
              onEnded={() => stemName === activeStem && !isLoopEnabled && setIsPlaying(false)}
              style={{ display: "none" }}
              crossOrigin="anonymous"
            />
          ))}
        </div>
      </main>

      {/* 4. Footer Master */}
      <footer className="master-footer">
        <div style={{ fontFamily: "IBM Plex Mono", fontSize: 13 }}>
          LUFS: <strong>{masterMetrics?.lufs || "--"}</strong> | 
          PICO: <strong style={{ color: "var(--bad)" }}>{masterMetrics?.true_peak_dbtp || "--"} dB</strong>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 24 }}>
          SESSÃO: <strong>{formatTrackLabel(job, "Sem Título")}</strong>
        </div>
        <button 
          className="btn btn-accent btn-xs" 
          style={{ marginLeft: "auto", padding: "10px 20px" }}
          onClick={onCreateStudyMixExport}
        >
          EXPORTAR MIXAGEM
        </button>
      </footer>
    </div>
  );
}

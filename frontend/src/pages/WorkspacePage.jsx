import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useWebAudioMixer } from "../hooks/useWebAudioMixer";

function getExportStateLabel(state) {
  if (state === "ready") {
    return "Pronto";
  }
  if (state === "failed") {
    return "Falhou";
  }
  if (state === "processing") {
    return "Processando";
  }
  return "Na fila";
}

function getExportStateClass(state) {
  if (state === "ready") {
    return "ready";
  }
  if (state === "failed") {
    return "failed";
  }
  return "processing";
}

function formatExportCreatedAt(value) {
  if (!value) {
    return "--";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "--";
  }

  return parsed.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatStemLabel(stemName) {
  const normalized = String(stemName || "").trim();
  if (!normalized) {
    return "Stem";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function toMeterHeight(levelValue) {
  const normalized = Number.isFinite(levelValue) ? levelValue : 60;
  return `${Math.max(10, Math.min(100, normalized))}%`;
}

export default function WorkspacePage({
  job,
  sessionCode,
  stemsList,
  getStemAudioUrl,
  mixLevels,
  updateMixLevel,
  mixStateLoading,
  mixStateSaving,
  mixStateError,
  exportJobs,
  exportJobsLoading,
  exportJobsError,
  exportActionLoading,
  exportActionMessage,
  onCreateStudyMixExport,
  onCreateStemsExport,
  onCreateCustomExport,
  onRetryExport,
  onRefreshExports,
  getExportFileUrl,
  masterMetrics,
  toFileName,
  onGoDiscover,
}) {
  const isReady = job?.state === "ready";
  const stemsToRender = stemsList;
  const hasMasterMetrics = Boolean(masterMetrics);
  const audioElementsRef = useRef({});
  const rafRef = useRef(null);
  const skipSeconds = 5;
  const [activeStem, setActiveStem] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoopEnabled, setIsLoopEnabled] = useState(false);
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [currentTimeSeconds, setCurrentTimeSeconds] = useState(0);
  const [soloStem, setSoloStem] = useState("");
  const [mutedStems, setMutedStems] = useState({});
  const [panLevels, setPanLevels] = useState({});

  const stemNames = useMemo(() => stemsToRender.map(([stemName]) => stemName), [stemsToRender]);
  const canUsePlayer = Boolean(isReady && stemNames.length > 0 && job?.job_id);

  const { initAudioContext, meters, masterNodes } = useWebAudioMixer({
    stemNames,
    audioElementsRef,
    mixLevels,
    panLevels,
    mutedStems,
    soloStem,
    isPlaying,
  });

  function stopRafLoop() {
    if (rafRef.current) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }

  function syncPlaybackProgress() {
    const activeAudio = audioElementsRef.current[activeStem];
    if (!activeAudio) {
      setCurrentTimeSeconds(0);
      return;
    }

    const duration = Number.isFinite(activeAudio.duration) ? activeAudio.duration : 0;
    const time = Number.isFinite(activeAudio.currentTime) ? activeAudio.currentTime : 0;

    setDurationSeconds(duration);
    setCurrentTimeSeconds(Math.min(time, duration || time));
    if (!activeAudio.paused) {
      rafRef.current = window.requestAnimationFrame(syncPlaybackProgress);
    }
  }

  async function playAllFromCurrentPosition() {
    if (!canUsePlayer) {
      return;
    }

    initAudioContext();

    const playables = stemNames
      .map((stemName) => audioElementsRef.current[stemName])
      .filter((audioNode) => Boolean(audioNode));

    if (!playables.length) {
      return;
    }

    try {
      await Promise.all(playables.map((audioNode) => audioNode.play()));
      setIsPlaying(true);
      stopRafLoop();
      rafRef.current = window.requestAnimationFrame(syncPlaybackProgress);
    } catch {
      setIsPlaying(false);
    }
  }

  function pauseAll() {
    stemNames.forEach((stemName) => {
      const audioNode = audioElementsRef.current[stemName];
      if (audioNode) {
        audioNode.pause();
      }
    });
    setIsPlaying(false);
    stopRafLoop();
  }

  function setCurrentTimeForAll(nextSeconds) {
    const safeSeconds = Math.max(0, nextSeconds || 0);
    stemNames.forEach((stemName) => {
      const audioNode = audioElementsRef.current[stemName];
      if (audioNode) {
        audioNode.currentTime = safeSeconds;
      }
    });
    setCurrentTimeSeconds(safeSeconds);
  }

  function handleTogglePlayback() {
    if (!canUsePlayer) {
      return;
    }

    if (isPlaying) {
      pauseAll();
      return;
    }

    playAllFromCurrentPosition();
  }

  function handleSeekOffset(offset) {
    if (!canUsePlayer) {
      return;
    }

    const maxDuration = durationSeconds || 0;
    const nextTime = Math.min(Math.max(currentTimeSeconds + offset, 0), maxDuration > 0 ? maxDuration : Number.MAX_SAFE_INTEGER);
    setCurrentTimeForAll(nextTime);
  }

  function handleSeekToStart() {
    if (!canUsePlayer) {
      return;
    }

    setCurrentTimeForAll(0);
  }

  function handleScrub(event) {
    const nextValue = Number(event.target.value);
    if (!Number.isFinite(nextValue)) {
      return;
    }

    setCurrentTimeForAll(nextValue);
  }

  function handleEnded(stemName) {
    if (stemName !== activeStem) {
      return;
    }

    if (isLoopEnabled) {
      setCurrentTimeForAll(0);
      playAllFromCurrentPosition();
      return;
    }

    setCurrentTimeSeconds(durationSeconds);
    setIsPlaying(false);
    stopRafLoop();
  }

  function toggleStemMute(stemName) {
    setMutedStems((previous) => ({
      ...previous,
      [stemName]: !previous[stemName],
    }));
  }

  function toggleStemSolo(stemName) {
    setSoloStem((previous) => (previous === stemName ? "" : stemName));
  }

  function formatClock(secondsValue) {
    const safeValue = Number.isFinite(secondsValue) ? Math.max(0, Math.floor(secondsValue)) : 0;
    const minutes = Math.floor(safeValue / 60);
    const seconds = safeValue % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function bindAudioNode(stemName, node) {
    if (!node) {
      delete audioElementsRef.current[stemName];
      return;
    }

    audioElementsRef.current[stemName] = node;
  }

  useEffect(() => {
    if (!stemNames.length) {
      setActiveStem("");
      setIsPlaying(false);
      setDurationSeconds(0);
      setCurrentTimeSeconds(0);
      setSoloStem("");
      setMutedStems({});
      stopRafLoop();
      return;
    }

    setActiveStem((previous) => (previous && stemNames.includes(previous) ? previous : stemNames[0]));
  }, [stemNames]);

  useEffect(() => {
    stemNames.forEach((stemName) => {
      const audioNode = audioElementsRef.current[stemName];
      if (!audioNode) {
        return;
      }

      const isMutedBySolo = Boolean(soloStem) && soloStem !== stemName;
      const isMutedByToggle = Boolean(mutedStems[stemName]);
      audioNode.muted = isMutedBySolo || isMutedByToggle;
    });
  }, [stemNames, soloStem, mutedStems]);

  useEffect(() => {
    stemNames.forEach((stemName) => {
      const audioNode = audioElementsRef.current[stemName];
      if (audioNode) {
        audioNode.loop = isLoopEnabled;
      }
    });
  }, [stemNames, isLoopEnabled]);

  useEffect(() => {
    // Usamos o useWebAudioMixer para volume, este bloco está desativado para nao interferir com os GainNodes.
  }, [stemNames, stemsToRender, mixLevels]);

  useEffect(() => {
    return () => {
      stopRafLoop();
    };
  }, []);

  const lufsLabel = hasMasterMetrics && Number.isFinite(masterMetrics.lufs) ? `${masterMetrics.lufs} LUFS` : "--";
  const truePeakLabel =
    hasMasterMetrics && Number.isFinite(masterMetrics.true_peak_dbtp) ? `${masterMetrics.true_peak_dbtp} dBTP` : "--";
  const headroomLabel =
    hasMasterMetrics && Number.isFinite(masterMetrics.headroom_db) ? `${masterMetrics.headroom_db} dB` : "--";
  const progressMax = Math.max(0, durationSeconds);
  const scrubValue = progressMax > 0 ? Math.min(currentTimeSeconds, progressMax) : 0;

  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>3. Workspace: ouvir, ajustar e exportar</h1>
          <p>Aqui estao reunidos player e mixer em linguagem de estacao profissional.</p>
        </div>
        <span className={`state ${isReady ? "ready" : "processing"}`}>{isReady ? "Pronta" : "Aguardando"}</span>
      </div>

      <section className="card animate-up" style={{ marginTop: 12, animationDelay: "60ms" }}>
        <div className="timeline">
          <article className="step done">
            <div className="name">1. Descobrir</div>
            <div className="meta">Fonte escolhida</div>
          </article>
          <article className="step done">
            <div className="name">2. Processamento</div>
            <div className="meta">Stems gerados</div>
          </article>
          <article className="step live">
            <div className="name">3. Workspace</div>
            <div className="meta">Ajuste fino de mix</div>
          </article>
          <article className="step">
            <div className="name">4. Biblioteca</div>
            <div className="meta">Salvar e reusar</div>
          </article>
        </div>
      </section>

      {!job && (
        <section className="card empty-state" style={{ marginTop: 12 }}>
          <h3>Nenhuma sessao carregada</h3>
          <p>Inicie o processamento em Descobrir e acompanhe em Processamento.</p>
          <button className="btn btn-primary" type="button" onClick={onGoDiscover}>
            Ir para Descobrir
          </button>
        </section>
      )}

      {job && (
        <div className="main-grid" style={{ marginTop: 14 }}>
          <section className="card animate-up">
            <section className="card pro-player" style={{ marginTop: 0 }}>
              <div className="pro-player-head">
                <div>
                  <h3>Player de referencia</h3>
                  <p className="inline-note" style={{ marginTop: 8 }}>
                    Escuta de qualidade para definir nivel, panorama e dinamica antes da exportacao.
                  </p>
                </div>
                <div className="deck-tags">
                  <span className="preview-chip">Sessao {sessionCode}</span>
                  <span className="preview-chip">Estado {isReady ? "Pronta" : "Em progresso"}</span>
                  <span className="preview-chip">Fonte {job?.selected_track?.source || "--"}</span>
                </div>
              </div>

              <div className="transport-row">
                <button className="transport-btn" type="button" onClick={handleSeekToStart} disabled={!canUsePlayer}>
                  |&lt;
                </button>
                <button
                  className="transport-btn"
                  type="button"
                  onClick={() => handleSeekOffset(-skipSeconds)}
                  disabled={!canUsePlayer}
                >
                  &lt;&lt; {skipSeconds}
                </button>
                <button className="transport-btn play" type="button" onClick={handleTogglePlayback} disabled={!canUsePlayer}>
                  {isPlaying ? "Pause" : "Play"}
                </button>
                <button
                  className="transport-btn"
                  type="button"
                  onClick={() => handleSeekOffset(skipSeconds)}
                  disabled={!canUsePlayer}
                >
                  {skipSeconds} &gt;&gt;
                </button>
                <button className="transport-btn" type="button" onClick={() => setIsLoopEnabled((previous) => !previous)} disabled={!canUsePlayer}>
                  &gt;|
                </button>
              </div>

              <div className="timeline-pro">
                <span className="timecode mono">{formatClock(currentTimeSeconds)}</span>
                <input
                  className="scrub"
                  type="range"
                  min="0"
                  max={progressMax || 1}
                  step="0.01"
                  value={scrubValue}
                  onChange={handleScrub}
                  disabled={!canUsePlayer}
                />
                <span className="timecode mono">{formatClock(durationSeconds)}</span>
              </div>

              <div className="player-tool-row">
                <div className="player-switches">
                  <button className={`pill-btn ${isLoopEnabled ? "active" : ""}`} type="button" onClick={() => setIsLoopEnabled((previous) => !previous)} disabled={!canUsePlayer}>
                    Loop
                  </button>
                  <button className="pill-btn" type="button" onClick={handleSeekToStart} disabled={!canUsePlayer}>
                    Reset
                  </button>
                  <button className="pill-btn" type="button" onClick={pauseAll} disabled={!canUsePlayer || !isPlaying}>
                    Stop
                  </button>
                  <button
                    className="pill-btn"
                    type="button"
                    onClick={() => {
                      setSoloStem("");
                      setMutedStems({});
                    }}
                    disabled={!canUsePlayer}
                  >
                    Limpar
                  </button>
                </div>

                <div className="player-meta-grid">
                  <div>
                    <span>Stem ativo</span>
                    <strong>{activeStem || "--"}</strong>
                  </div>
                  <div>
                    <span>Duracao</span>
                    <strong>{formatClock(durationSeconds)}</strong>
                  </div>
                  <div>
                    <span>Modo</span>
                    <strong>{isLoopEnabled ? "Loop" : "Linear"}</strong>
                  </div>
                </div>
              </div>

              <div className="player-switches" style={{ marginTop: 8 }}>
                {stemNames.map((stemName) => (
                  <button
                    key={`deck-${stemName}`}
                    className={`pill-btn ${activeStem === stemName ? "active" : ""}`}
                    type="button"
                    onClick={() => setActiveStem(stemName)}
                    disabled={!canUsePlayer}
                  >
                    {formatStemLabel(stemName)}
                  </button>
                ))}
              </div>

              <div className="meter-bridge" aria-hidden="true">
                <div className="meter-column">
                  <small>L</small>
                  <div className="meter-rail">
                    <i style={{ height: toMeterHeight(meters?.masterL || 0) }} />
                  </div>
                  <span>{Math.round(meters?.masterL || 0)}%</span>
                </div>
                <div className="meter-column">
                  <small>R</small>
                  <div className="meter-rail">
                    <i style={{ height: toMeterHeight(meters?.masterR || 0) }} />
                  </div>
                  <span>{Math.round(meters?.masterR || 0)}%</span>
                </div>
              </div>

              <div className="wave-overview oscilloscope" aria-hidden="true">
                <canvas 
                  id="master-oscilloscope" 
                  width="800" 
                  height="120" 
                  style={{ width: "100%", height: "100%", display: "block", background: "none" }}
                  ref={(canvas) => {
                    // Animacao simples para renderizar o AnalyserL da master para representação
                    if (!canvas || !masterNodes) return;
                    const ctx = canvas.getContext("2d");
                    const draw = () => {
                       if (!ctx || !isPlaying) return;
                       const bufferLength = masterNodes.analyserL.frequencyBinCount;
                       const dataArray = new Uint8Array(bufferLength);
                       masterNodes.analyserL.getByteTimeDomainData(dataArray);

                       ctx.clearRect(0, 0, canvas.width, canvas.height);
                       ctx.lineWidth = 2;
                       ctx.strokeStyle = "rgba(40, 200, 180, 0.8)";
                       ctx.beginPath();
                       
                       const sliceWidth = canvas.width * 1.0 / bufferLength;
                       let x = 0;
                       
                       for(let i = 0; i < bufferLength; i++) {
                         const v = dataArray[i] / 128.0;
                         const y = v * canvas.height / 2;
                         if(i === 0) ctx.moveTo(x, y);
                         else ctx.lineTo(x, y);
                         x += sliceWidth;
                       }
                       ctx.lineTo(canvas.width, canvas.height / 2);
                       ctx.stroke();
                       if (isPlaying) requestAnimationFrame(draw);
                    };
                    draw();
                  }}
                ></canvas>
              </div>
            </section>

            <h3 style={{ marginTop: 14 }}>Mixer profissional por stem</h3>

            {mixStateLoading && <p className="inline-note">Carregando estado salvo do mixer...</p>}
            {!mixStateLoading && mixStateSaving && <p className="inline-note">Salvando ajustes do mixer...</p>}
            {!mixStateLoading && !mixStateSaving && !mixStateError && (
              <p className="inline-note">Ajustes salvos automaticamente para esta sessao.</p>
            )}
            {mixStateError && <p className="error-banner">{mixStateError}</p>}

            {stemsToRender.length === 0 ? (
              <p className="inline-note">Nenhum stem disponivel para esta sessao.</p>
            ) : (
              <div className="strip-grid">
                {stemsToRender.map(([stemName]) => (
                  <article className="channel-strip" key={stemName}>
                    <div className="strip-head">
                      <strong>{formatStemLabel(stemName)}</strong>
                      <span>{mixLevels[stemName] ?? 60}%</span>
                    </div>

                    <div className="strip-inserts">
                      <span>EQ</span>
                      <span>Comp</span>
                      <span>Tone</span>
                    </div>

                    <div className="strip-meter-wrap" aria-hidden="true">
                      <div className="strip-meter">
                        <i style={{ height: toMeterHeight(meters?.stems?.[stemName] || 0) }} />
                      </div>
                      <small>{Math.round(meters?.stems?.[stemName] || 0)}%</small>
                    </div>

                    <div className="strip-control">
                      <label>Pan</label>
                      <input 
                        type="range" 
                        min="-100" 
                        max="100" 
                        value={panLevels[stemName] || 0} 
                        onChange={(e) => setPanLevels(prev => ({...prev, [stemName]: Number(e.target.value)}))}
                        disabled={!isReady} 
                      />
                    </div>

                    <div className="strip-control">
                      <label>Send FX</label>
                      <input type="range" min="0" max="100" value="20" readOnly disabled={!isReady} />
                    </div>

                    <div className="strip-control">
                      <label>Fader</label>
                      <input
                        data-mix-slider
                        name={stemName}
                        type="range"
                        min="0"
                        max="100"
                        value={mixLevels[stemName] ?? 60}
                        onChange={(event) => updateMixLevel(stemName, Number(event.target.value))}
                        disabled={!isReady}
                      />
                      <div className="slider-meta">
                        <span>Nivel</span>
                        <strong>{mixLevels[stemName] ?? 60}%</strong>
                      </div>
                    </div>

                    <div className="channel-controls">
                      <button
                        className={`pill-btn ${soloStem === stemName ? "active" : ""}`}
                        type="button"
                        onClick={() => toggleStemSolo(stemName)}
                        disabled={!canUsePlayer}
                      >
                        Solo
                      </button>
                      <button
                        className={`pill-btn ${mutedStems[stemName] ? "active" : ""}`}
                        type="button"
                        onClick={() => toggleStemMute(stemName)}
                        disabled={!canUsePlayer}
                      >
                        Mute
                      </button>
                    </div>

                    {job?.job_id && (
                      <audio
                        ref={(node) => bindAudioNode(stemName, node)}
                        preload="metadata"
                        crossOrigin="anonymous"
                        src={getStemAudioUrl(job.job_id, stemName)}
                        onLoadedMetadata={(event) => {
                          if (stemName !== activeStem) {
                            return;
                          }

                          const nextDuration = Number.isFinite(event.currentTarget.duration)
                            ? event.currentTarget.duration
                            : 0;
                          setDurationSeconds(nextDuration);
                        }}
                        onTimeUpdate={(event) => {
                          if (stemName !== activeStem || !event.currentTarget || !isPlaying) {
                            return;
                          }

                          const current = Number.isFinite(event.currentTarget.currentTime)
                            ? event.currentTarget.currentTime
                            : 0;
                          setCurrentTimeSeconds(current);
                        }}
                        onEnded={() => handleEnded(stemName)}
                        style={{ display: "none" }}
                      />
                    )}
                  </article>
                ))}
              </div>
            )}

            <section className="card master-pro" style={{ marginTop: 12 }}>
              <h3>Master bus</h3>

              <div className="master-grid">
                <div className="metric">
                  <div className="label">Loudness</div>
                  <div className="value short">{lufsLabel}</div>
                </div>
                <div className="metric">
                  <div className="label">True Peak</div>
                  <div className="value short">{truePeakLabel}</div>
                </div>
                <div className="metric">
                  <div className="label">Headroom</div>
                  <div className="value short">{headroomLabel}</div>
                </div>
                <div className="metric">
                  <div className="label">Device</div>
                  <div className="value short">{job?.separation_device ? String(job.separation_device).toUpperCase() : "--"}</div>
                </div>
              </div>

              <div className="slider-wrap" style={{ marginTop: 10 }}>
                <input
                  data-master-slider
                  type="range"
                  min="0"
                  max="100"
                  value={mixLevels.master}
                  onChange={(event) => updateMixLevel("master", Number(event.target.value))}
                  disabled={!isReady}
                />
                <div className="slider-meta">
                  <span>Master gain</span>
                  <strong data-master-value>{mixLevels.master}%</strong>
                </div>
              </div>
            </section>
          </section>

          <aside className="stack animate-up" style={{ animationDelay: "90ms" }}>
            <section className="card action-panel">
              <h3>Exportacao simplificada</h3>

              <div className="session-list" style={{ marginTop: 10 }}>
                <article className="session-item">
                  <div>
                    <div className="title">Mix para estudo</div>
                    <div className="meta">Preset study_mix em WAV unico</div>
                  </div>
                  <button
                    className="btn btn-subtle"
                    type="button"
                    onClick={onCreateStudyMixExport}
                    disabled={!isReady || Boolean(exportActionLoading)}
                  >
                    Exportar
                  </button>
                </article>

                <article className="session-item">
                  <div>
                    <div className="title">Stems individuais</div>
                    <div className="meta">Preset stems em ZIP</div>
                  </div>
                  <button
                    className="btn btn-subtle"
                    type="button"
                    onClick={onCreateStemsExport}
                    disabled={!isReady || Boolean(exportActionLoading)}
                  >
                    Exportar
                  </button>
                </article>
              </div>

              {exportActionMessage && <p className="inline-note">{exportActionMessage}</p>}

              <div className="input-row" style={{ marginTop: 10 }}>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={onCreateStudyMixExport}
                  disabled={!isReady || Boolean(exportActionLoading)}
                >
                  Exportar mix
                </button>
                <button
                  className="btn btn-accent"
                  type="button"
                  onClick={onCreateStemsExport}
                  disabled={!isReady || Boolean(exportActionLoading)}
                >
                  Baixar stems
                </button>
              </div>

              <div className="input-row" style={{ marginTop: 10 }}>
                <button
                  className="btn btn-subtle"
                  type="button"
                  onClick={onCreateCustomExport}
                  disabled={!isReady || Boolean(exportActionLoading)}
                >
                  Exportacao custom
                </button>
                <button className="btn btn-subtle" type="button" onClick={onRefreshExports} disabled={exportJobsLoading}>
                  Atualizar exports
                </button>
              </div>

              {!isReady && (
                <p className="inline-note">Exportacao disponivel apenas quando a sessao estiver no estado pronta.</p>
              )}

              {exportJobsLoading && <p className="inline-note">Carregando jobs de exportacao...</p>}
              {exportJobsError && <p className="error-banner">{exportJobsError}</p>}

              {!exportJobsLoading && !exportJobsError && exportJobs.length === 0 && (
                <p className="inline-note">Nenhum export criado para esta sessao.</p>
              )}

              {exportJobs.length > 0 && (
                <div className="session-list" style={{ marginTop: 10 }}>
                  {exportJobs.map((exportJob) => {
                    const outputFiles = Array.isArray(exportJob.output_files) ? exportJob.output_files : [];
                    const exportStateClass = getExportStateClass(exportJob.state);
                    const exportId = exportJob.export_id || "unknown";
                    return (
                      <article className="session-item" key={exportId}>
                        <div>
                          <div className="title">
                            {getExportStateLabel(exportJob.state)} | {String(exportJob.preset || "preset").toUpperCase()}
                          </div>
                          <div className="meta">
                            {String(exportJob.format || "wav").toUpperCase()} | progresso {exportJob.progress}% | {formatExportCreatedAt(exportJob.created_at)}
                          </div>

                          {exportJob.error && <div className="meta">Erro: {exportJob.error}</div>}

                          {outputFiles.length > 0 && (
                            <div className="table-actions" style={{ marginTop: 8 }}>
                              {outputFiles.map((fileItem) => {
                                const downloadUrl =
                                  fileItem.download_url ||
                                  getExportFileUrl(exportJob.session_id, exportId, fileItem.file_name);
                                return (
                                  <a
                                    key={`${exportId}:${fileItem.file_name}`}
                                    className="btn btn-subtle"
                                    href={downloadUrl}
                                    download={fileItem.file_name}
                                  >
                                    Baixar {fileItem.file_name}
                                  </a>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        <div className="table-actions">
                          <span className={`state ${exportStateClass}`}>{getExportStateLabel(exportJob.state)}</span>
                          {exportJob.state === "failed" && (
                            <button className="btn btn-subtle" type="button" onClick={() => onRetryExport(exportJob)}>
                              Retry
                            </button>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}

              <a className="btn btn-subtle" href="/?page=library">
                Salvar e ir para biblioteca
              </a>
            </section>

            <section className="card">
              <h3>Arquivos da sessao</h3>
              <table className="library-table" aria-label="arquivos de stems">
                <thead>
                  <tr>
                    <th>Stem</th>
                    <th>Formato</th>
                    <th>Arquivo</th>
                  </tr>
                </thead>
                <tbody>
                  {stemsToRender.length === 0 ? (
                    <tr>
                      <td colSpan={3}>Nenhum arquivo de stem disponivel.</td>
                    </tr>
                  ) : (
                    stemsToRender.map(([stemName, path]) => (
                      <tr key={stemName}>
                        <td>{formatStemLabel(stemName)}</td>
                        <td>WAV</td>
                        <td>{toFileName(path)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <p className="footer-note">Sessao visual: {sessionCode}. UUID segue apenas no backend.</p>
            </section>
          </aside>
        </div>
      )}
    </>
  );
}

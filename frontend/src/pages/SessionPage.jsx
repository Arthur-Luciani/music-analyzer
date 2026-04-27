function formatEventTime(timestamp) {
  if (!timestamp) {
    return "--:--:--";
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return "--:--:--";
  }

  return parsed.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEta(seconds) {
  if (!Number.isFinite(seconds)) {
    return "--";
  }

  const normalized = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(normalized / 60);
  const remainder = normalized % 60;
  return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
}

function getEventLevelClass(level) {
  if (level === "error") {
    return "failed";
  }
  if (level === "warning") {
    return "download";
  }
  return "ready";
}

function formatStemEnergy(value) {
  if (!Number.isFinite(value)) {
    return "Energia indisponivel";
  }
  return `${value}% energia`;
}

export default function SessionPage({
  job,
  sessionCode,
  error,
  processingFacts,
  sessionStemPreview,
  setStemAudioRef,
  handlePlayStemPreview,
  sessionEvents,
  sessionEventsLoading,
  sessionEventsError,
  getStateBadgeClass,
  getStateBadgeLabel,
  onGoDiscover,
  onGoWorkspace,
}) {
  const hasJob = Boolean(job);
  const isReady = job?.state === "ready";
  const stateClass = getStateBadgeClass(job?.state);
  const stateLabel = getStateBadgeLabel(job?.state);
  const etaLabel =
    Number.isFinite(job?.estimated_remaining_seconds) && job.estimated_remaining_seconds >= 0
      ? formatEta(job.estimated_remaining_seconds)
      : processingFacts?.remaining || "--";
  const separationDeviceLabel = job?.separation_device ? String(job.separation_device).toUpperCase() : "--";
  const renderedEvents = Array.isArray(sessionEvents)
    ? [...sessionEvents].slice(-10).reverse()
    : [];

  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>Processamento da sessao {sessionCode}</h1>
          <p>
            Acompanhe o estado em tempo real do pipeline. O identificador tecnico continua no backend, enquanto a
            interface usa um codigo amigavel.
          </p>
        </div>
        <span className={`state ${stateClass}`}>{stateLabel}</span>
      </div>

      {!hasJob && (
        <section className="card empty-state" style={{ marginTop: 12 }}>
          <h3>Nenhuma sessao ativa</h3>
          <p>Inicie uma busca em Descobrir para acompanhar um processamento.</p>
          <button className="btn btn-primary" type="button" onClick={onGoDiscover}>
            Ir para Descobrir
          </button>
        </section>
      )}

      {hasJob && (
        <section className="card animate-up" style={{ marginTop: 12, animationDelay: "70ms" }}>
          <div className="timeline">
            <article className={`step ${job.state !== "queued" ? "done" : "live"}`}>
              <div className="name">1. Fonte validada</div>
              <div className="meta">Codigo {sessionCode}</div>
            </article>
            <article
              className={`step ${
                job.state === "downloading" || job.state === "separating" || job.state === "ready" ? "done" : ""
              }`}
            >
              <div className="name">2. Download</div>
              <div className="meta">Estado downloading</div>
            </article>
            <article className={`step ${job.state === "separating" ? "live" : job.state === "ready" ? "done" : ""}`}>
              <div className="name">3. Separacao de stems</div>
              <div className="meta">Estado separating</div>
            </article>
            <article className={`step ${job.state === "ready" ? "done" : job.state === "failed" ? "failed" : ""}`}>
              <div className="name">4. Finalizacao</div>
              <div className="meta">Estado ready</div>
            </article>
          </div>

          <div className="progress-panel">
            <div className="progress-rail">
              <i style={{ width: `${job.progress || 0}%` }} />
            </div>
            <div className="progress-captions">
              <strong>
                Progresso geral <span>{job.progress || 0}%</span>
              </strong>
              <span>{job.message || "Aguardando atualizacoes"}</span>
            </div>
          </div>

          <div className="main-grid" style={{ marginTop: 12 }}>
            <div className="card wave-preview">
              <h3>Pre-visualizacao de analise</h3>

              {!isReady && (
                <>
                  {processingFacts && (
                    <div className="analysis-facts">
                      <span className="fact-chip">
                        Analisado: {processingFacts.analyzed} / {processingFacts.total}
                      </span>
                      <span className="fact-chip">Restante estimado: {processingFacts.remaining}</span>
                    </div>
                  )}

                  <p className="inline-note">{job.error ? `Erro: ${job.error}` : "Pipeline em execucao com atualizacao ao vivo."}</p>
                </>
              )}

              {isReady && (
                <>
                  <p className="inline-note">Stems extraidos. Confira energia relativa e ouca um preview curto.</p>
                  <div className="preview-grid">
                    {sessionStemPreview.map((item) => (
                      <article className="stem-preview-card" key={item.stemName}>
                        <div className="stem-preview-head">
                          <strong>{item.stemName}</strong>
                          <span>{formatStemEnergy(item.energy)}</span>
                        </div>

                        <div className="energy-track" aria-hidden="true">
                          <i style={{ width: `${Number.isFinite(item.energy) ? item.energy : 0}%` }} />
                        </div>

                        <div className="stem-preview-meta">
                          <span>{item.fileName}</span>
                          <span>{item.fileSizeLabel}</span>
                        </div>

                        <audio
                          ref={(node) => setStemAudioRef(item.stemName, node)}
                          className="preview-audio"
                          controls
                          preload="metadata"
                          src={item.audioUrl}
                        />

                        <button
                          className="btn btn-subtle preview-btn"
                          type="button"
                          onClick={() => handlePlayStemPreview(item.stemName)}
                        >
                          Preview 10s
                        </button>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="stack">
              <section className="card">
                <h3>Telemetria da sessao</h3>
                <div className="metric-grid" style={{ marginTop: 10 }}>
                  <div className="metric">
                    <div className="label">Sessao</div>
                    <div className="value">{sessionCode}</div>
                  </div>
                  <div className="metric">
                    <div className="label">Estado</div>
                    <div className="value">{job.state || "queued"}</div>
                  </div>
                  <div className="metric">
                    <div className="label">Progresso</div>
                    <div className="value">{job.progress || 0}%</div>
                  </div>
                  <div className="metric">
                    <div className="label">Fonte</div>
                    <div className="value short">{job.selected_track?.source || "--"}</div>
                  </div>
                  <div className="metric">
                    <div className="label">ETA</div>
                    <div className="value short">{etaLabel}</div>
                  </div>
                  <div className="metric">
                    <div className="label">Device</div>
                    <div className="value short">{separationDeviceLabel}</div>
                  </div>
                </div>
              </section>

              <section className="card">
                <h3>Log de eventos</h3>
                {sessionEventsLoading && <p className="inline-note">Carregando eventos...</p>}

                {sessionEventsError && (
                  <p className="error-banner" style={{ marginBottom: 0 }}>
                    {sessionEventsError}
                  </p>
                )}

                {!sessionEventsLoading && !sessionEventsError && renderedEvents.length === 0 && (
                  <p className="inline-note">Ainda nao ha eventos registrados para esta sessao.</p>
                )}

                {renderedEvents.length > 0 && (
                  <div className="session-list" style={{ marginTop: 10 }}>
                    {renderedEvents.map((event, index) => {
                      const eventLevel = String(event.level || "info").toLowerCase();
                      const eventClass = getEventLevelClass(eventLevel);
                      const eventProgress = Number.isFinite(event.progress) ? ` (${event.progress}%)` : "";

                      return (
                        <article className="session-item" key={`${event.timestamp || "evt"}-${event.stage || "stage"}-${index}`}>
                          <div>
                            <div className="title">
                              {formatEventTime(event.timestamp)} | {event.stage || "evento"}
                            </div>
                            <div className="meta">
                              {event.message || "Sem detalhes"}
                              {eventProgress}
                            </div>
                          </div>
                          <span className={`state ${eventClass}`}>{eventLevel}</span>
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>
          </div>

          {job.state === "ready" && (
            <div className="session-actions">
              <button className="btn btn-primary" type="button" onClick={onGoWorkspace}>
                Ir para workspace
              </button>
            </div>
          )}

          {error && <p className="error-banner">{error}</p>}
        </section>
      )}
    </>
  );
}

function toCompatibilityLabel(scoreValue) {
  if (!Number.isFinite(scoreValue)) {
    return "N/D";
  }
  return `${Math.max(0, Math.min(100, Math.round(scoreValue)))}%`;
}

function toCompatibilityClass(scoreValue) {
  if (!Number.isFinite(scoreValue)) {
    return "unknown";
  }
  if (scoreValue >= 80) {
    return "high";
  }
  if (scoreValue >= 55) {
    return "medium";
  }
  return "low";
}

function toBreakdownLabel(metricKey) {
  const normalized = String(metricKey || "").trim().toLowerCase();
  if (normalized === "title") {
    return "Título";
  }
  if (normalized === "artist") {
    return "Artista";
  }
  if (normalized === "duration") {
    return "Duração";
  }
  if (normalized === "quality") {
    return "Qualidade";
  }
  return normalized || "Métrica";
}

export default function DiscoverPage({
  handleSubmit,
  query,
  setQuery,
  processing,
  runSearch,
  loading,
  searching,
  candidates,
  selectedSourceId,
  setSelectedSourceId,
  formatDuration,
  selectedCandidate,
  sessionCode,
  error,
}) {
  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>Descobrir</h1>
        </div>
        <span className="state processing">Pronto</span>
      </div>

      <div className="main-grid" style={{ marginTop: 12 }}>
        <section className="card hero-card animate-up" style={{ animationDelay: "90ms" }}>
          <h2 style={{ marginTop: 10 }}>Buscar e validar fonte</h2>

          <form className="field-grid" onSubmit={handleSubmit}>
            <label htmlFor="query">Buscar faixa ou colar URL</label>
            <div className="input-row">
              <input
                id="query"
                type="text"
                value={query}
                placeholder="Ex: Basket Case Green Day ou URL do YouTube"
                onChange={(event) => setQuery(event.target.value)}
                disabled={processing}
              />
              <button type="button" className="btn btn-subtle" onClick={() => runSearch()} disabled={loading}>
                {searching ? "Buscando..." : "Buscar fontes"}
              </button>
              <button type="submit" className="btn btn-accent" disabled={loading}>
                {processing ? "Criando rascunho..." : "Continuar"}
              </button>
            </div>
          </form>

          {candidates.length > 0 && (
            <div className="source-list">
              {candidates.map((candidate, index) => {
                const isSelected = selectedSourceId === candidate.source_id;
                const compatibilityScore = Number(candidate.compatibility_score);
                const compatibilityLabel = toCompatibilityLabel(compatibilityScore);
                const compatibilityClass = toCompatibilityClass(compatibilityScore);
                const breakdownEntries = Object.entries(candidate.compatibility_breakdown || {}).filter(
                  ([, value]) => Number.isFinite(Number(value))
                );

                return (
                  <article
                    key={candidate.source_id}
                    className={`source-item ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedSourceId(candidate.source_id)}
                  >
                    <div className="source-rank">{index + 1}</div>
                    <div className="source-main">
                      <div className="source-title">{candidate.title}</div>
                      <div className="source-meta">
                        {candidate.artist} | {formatDuration(candidate.duration_seconds)} | {candidate.source}
                      </div>
                      <div className="compatibility-row">
                        <span className={`compatibility-pill ${compatibilityClass}`}>Compatibilidade {compatibilityLabel}</span>
                        {breakdownEntries.length > 0 && (
                          <div className="compatibility-breakdown">
                            {breakdownEntries.map(([metricKey, value]) => (
                              <span className="compatibility-chip" key={`${candidate.source_id}:${metricKey}`}>
                                {toBreakdownLabel(metricKey)} {Math.round(Number(value))}%
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="source-actions">
                      <label className="pick-wrap" onClick={(event) => event.stopPropagation()}>
                        <input
                          type="radio"
                          name="selected-source"
                          checked={isSelected}
                          onChange={() => setSelectedSourceId(candidate.source_id)}
                        />
                        <span>Selecionar</span>
                      </label>
                      <a
                        href={candidate.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-link"
                        onClick={(event) => event.stopPropagation()}
                      >
                        Abrir
                      </a>
                    </div>
                  </article>
                );
              })}
            </div>
          )}

          {error && <p className="error-banner">{error}</p>}
        </section>

        <aside className="stack">
          <section className="card action-panel animate-up" style={{ animationDelay: "120ms" }}>
            <h3>Decisão atual</h3>
            <div className="kv-list">
              <div className="kv">
                <span>Faixa</span>
                <strong>{selectedCandidate?.title || "--"}</strong>
              </div>
              <div className="kv">
                <span>Fonte</span>
                <strong>{selectedCandidate?.source || "--"}</strong>
              </div>
              <div className="kv">
                <span>Duração</span>
                <strong>
                  {selectedCandidate ? formatDuration(selectedCandidate.duration_seconds) : "--"}
                </strong>
              </div>
              <div className="kv">
                <span>Sessão</span>
                <strong className="mono">{sessionCode}</strong>
              </div>
              <div className="kv">
                <span>Compatibilidade</span>
                <strong>
                  {selectedCandidate
                    ? toCompatibilityLabel(Number(selectedCandidate.compatibility_score))
                    : "--"}
                </strong>
              </div>
            </div>
            <p className="inline-note">Próximo passo: confirmar artista e música.</p>
          </section>

          <section className="card animate-up" style={{ animationDelay: "170ms" }}>
            <h3>Regras simples da jornada</h3>
            <ul className="flow-checklist">
              <li>Escolher apenas uma fonte por sessão.</li>
              <li>Ajustes de áudio ficam apenas no workspace.</li>
              <li>Biblioteca serve para retomar e duplicar sessões.</li>
            </ul>
          </section>
        </aside>
      </div>
    </>
  );
}

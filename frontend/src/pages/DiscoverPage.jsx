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
    return "Titulo";
  }
  if (normalized === "artist") {
    return "Artista";
  }
  if (normalized === "duration") {
    return "Duracao";
  }
  if (normalized === "quality") {
    return "Qualidade";
  }
  return normalized || "Metrica";
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
          <h1>1. Escolha a faixa certa</h1>
          <p>Primeiro passo: buscar e confirmar uma unica fonte para evitar retrabalho no processamento.</p>
        </div>
        <span className="state processing">Inicio</span>
      </div>

      <section className="card animate-up" style={{ marginTop: 12, animationDelay: "70ms" }}>
        <div className="timeline">
          <article className="step live">
            <div className="name">1. Descobrir</div>
            <div className="meta">Escolha da fonte</div>
          </article>
          <article className="step">
            <div className="name">2. Processamento</div>
            <div className="meta">Separacao automatica</div>
          </article>
          <article className="step">
            <div className="name">3. Workspace</div>
            <div className="meta">Mix e preview</div>
          </article>
          <article className="step">
            <div className="name">4. Biblioteca</div>
            <div className="meta">Reuso e historico</div>
          </article>
        </div>
      </section>

      <div className="main-grid" style={{ marginTop: 12 }}>
        <section className="card hero-card animate-up" style={{ animationDelay: "90ms" }}>
          <span className="kicker">Passo unico</span>
          <h2 style={{ marginTop: 10 }}>Buscar e validar a melhor fonte</h2>
          <p className="hero-copy" style={{ marginTop: 8 }}>
            A tela agora tem um unico objetivo: voce escolhe uma fonte e segue para processamento. Sem telemetria aqui.
          </p>

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
                {processing ? "Processando..." : "Iniciar sessao"}
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
            <h3>Decisao atual</h3>
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
                <span>Duracao</span>
                <strong>
                  {selectedCandidate ? formatDuration(selectedCandidate.duration_seconds) : "--"}
                </strong>
              </div>
              <div className="kv">
                <span>Sessao</span>
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
            <p className="inline-note">Proximo passo: acompanhar separacao em tempo real.</p>
          </section>

          <section className="card animate-up" style={{ animationDelay: "170ms" }}>
            <h3>Regras simples da jornada</h3>
            <ul className="flow-checklist">
              <li>Escolher apenas uma fonte por sessao.</li>
              <li>Ajustes de audio ficam apenas no workspace.</li>
              <li>Biblioteca serve para retomar e duplicar sessoes.</li>
            </ul>
          </section>
        </aside>
      </div>
    </>
  );
}

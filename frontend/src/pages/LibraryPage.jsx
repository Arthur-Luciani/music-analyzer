function formatSessionDate(dateValue) {
  if (!dateValue) {
    return "--";
  }

  const parsed = new Date(dateValue);
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

export default function LibraryPage({
  sessions,
  total,
  page,
  totalPages,
  filters,
  loading,
  error,
  actionLoading,
  actionMessage,
  getStateBadgeLabel,
  getStateBadgeClass,
  onFilterChange,
  onApplyFilters,
  onClearFilters,
  onRetry,
  onPrevPage,
  onNextPage,
  onOpenWorkspace,
  onTrackSession,
  onDuplicate,
  onReprocess,
  isProcessingStatus,
}) {
  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>4. Biblioteca: retomar e reutilizar</h1>
          <p>Ultimo passo da jornada: encontrar uma sessao pronta e continuar do ponto certo.</p>
        </div>
        <span className="state ready">Organizada</span>
      </div>

      <section className="card animate-up" style={{ marginTop: 12, animationDelay: "50ms" }}>
        <div className="timeline">
          <article className="step done">
            <div className="name">1. Descobrir</div>
            <div className="meta">Fonte definida</div>
          </article>
          <article className="step done">
            <div className="name">2. Processamento</div>
            <div className="meta">Separacao concluida</div>
          </article>
          <article className="step done">
            <div className="name">3. Workspace</div>
            <div className="meta">Mixagem realizada</div>
          </article>
          <article className="step live">
            <div className="name">4. Biblioteca</div>
            <div className="meta">Retomada e reuso</div>
          </article>
        </div>
      </section>

      <section className="card animate-up" style={{ marginTop: 12, animationDelay: "60ms" }}>
        <div className="search-filter">
          <input
            type="text"
            value={filters.query}
            placeholder="Buscar por sessao, faixa ou artista"
            aria-label="buscar na biblioteca"
            onChange={(event) => onFilterChange("query", event.target.value)}
          />
          <select
            aria-label="filtro de estado"
            value={filters.status}
            onChange={(event) => onFilterChange("status", event.target.value)}
          >
            <option value="">Todos os estados</option>
            <option value="queued">Na fila</option>
            <option value="downloading">Baixando</option>
            <option value="separating">Separando</option>
            <option value="ready">Pronta</option>
            <option value="failed">Falhou</option>
          </select>
          <input
            type="date"
            aria-label="criado de"
            value={filters.created_from}
            onChange={(event) => onFilterChange("created_from", event.target.value)}
          />
          <input
            type="date"
            aria-label="criado ate"
            value={filters.created_to}
            onChange={(event) => onFilterChange("created_to", event.target.value)}
          />
          <button className="btn btn-subtle" type="button" onClick={onApplyFilters} disabled={loading}>
            Aplicar filtros
          </button>
          <button className="btn btn-subtle" type="button" onClick={onClearFilters} disabled={loading}>
            Limpar
          </button>
          <a className="btn btn-accent" href="/?page=discover">
            Nova separacao
          </a>
        </div>

        {actionMessage && <p className="inline-note">{actionMessage}</p>}

        {error && (
          <div className="library-alert-row">
            <p className="error-banner" style={{ marginTop: 10, marginBottom: 0 }}>
              {error}
            </p>
            <button className="btn btn-subtle" type="button" onClick={onRetry} disabled={loading}>
              Tentar novamente
            </button>
          </div>
        )}

        {loading && <p className="inline-note">Carregando sessoes...</p>}

        {!loading && sessions.length === 0 && (
          <section className="card empty-state" style={{ marginTop: 12 }}>
            <h3>Nenhuma sessao encontrada</h3>
            <p>Ajuste os filtros ou tente novamente para recarregar a biblioteca.</p>
            <button className="btn btn-subtle" type="button" onClick={onRetry}>
              Recarregar biblioteca
            </button>
          </section>
        )}

        {!loading && sessions.length > 0 && (
          <>
            <table className="library-table" aria-label="historico de sessoes" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>Sessao</th>
                  <th>Faixa</th>
                  <th>Criada em</th>
                  <th>Status</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => {
                  const stateClass = getStateBadgeClass(session.status);
                  const rowIsBusy = actionLoading.includes(session.session_id);
                  return (
                    <tr key={session.session_id}>
                      <td>{session.session_code}</td>
                      <td>{session.track_title || "Faixa nao informada"}</td>
                      <td>{formatSessionDate(session.created_at)}</td>
                      <td>
                        <span className={`state ${stateClass}`}>{getStateBadgeLabel(session.status)}</span>
                      </td>
                      <td>
                        <div className="table-actions">
                          {session.status === "ready" && (
                            <button
                              className="btn btn-subtle"
                              type="button"
                              onClick={() => onOpenWorkspace(session.session_id)}
                              disabled={rowIsBusy || loading}
                            >
                              Abrir workspace
                            </button>
                          )}

                          {(isProcessingStatus(session.status) || session.status === "failed") && (
                            <button
                              className="btn btn-subtle"
                              type="button"
                              onClick={() => onTrackSession(session.session_id)}
                              disabled={rowIsBusy || loading}
                            >
                              Acompanhar
                            </button>
                          )}

                          <button
                            className="btn btn-subtle"
                            type="button"
                            onClick={() => onDuplicate(session.session_id)}
                            disabled={rowIsBusy || loading}
                          >
                            Duplicar
                          </button>

                          <button
                            className="btn btn-subtle"
                            type="button"
                            onClick={() => onReprocess(session.session_id)}
                            disabled={rowIsBusy || loading}
                          >
                            Reprocessar
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="library-pagination">
              <p className="inline-note" style={{ marginTop: 0 }}>
                Pagina {page} de {totalPages} | {total} sessoes
              </p>
              <div className="table-actions">
                <button className="btn btn-subtle" type="button" onClick={onPrevPage} disabled={page <= 1 || loading}>
                  Anterior
                </button>
                <button
                  className="btn btn-subtle"
                  type="button"
                  onClick={onNextPage}
                  disabled={page >= totalPages || loading}
                >
                  Proxima
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}

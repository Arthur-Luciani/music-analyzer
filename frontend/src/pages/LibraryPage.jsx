import { formatTrackLabel } from "../utils/formatters";

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
  onDelete,
  onResumeDraft,
  isProcessingStatus,
}) {
  return (
    <>
      <div className="page-title-row animate-up">
        <div>
          <h1>Biblioteca</h1>
        </div>
        <span className="state ready">Organizada</span>
      </div>


      <section className="card animate-up" style={{ marginTop: 12, animationDelay: "60ms" }}>
        <form
          className="search-filter"
          onSubmit={(event) => {
            event.preventDefault();
            onApplyFilters();
          }}
        >
          <input
            type="text"
            value={filters.query}
            placeholder="Buscar por sessão, faixa ou artista"
            aria-label="buscar na biblioteca"
            onChange={(event) => onFilterChange("query", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClearFilters();
            }}
          />
          <select
            aria-label="filtro de estado"
            value={filters.status}
            onChange={(event) => onFilterChange("status", event.target.value)}
          >
            <option value="">Todos os estados</option>
            <option value="queued">Rascunho</option>
            <option value="downloading">Baixando</option>
            <option value="separating">Separando</option>
            <option value="ready">Pronta</option>
            <option value="failed">Falhou</option>
          </select>
          <div className="filter-group">
            <span className="filter-label">De:</span>
            <input
              type="date"
              aria-label="criado de"
              value={filters.created_from}
              onChange={(event) => onFilterChange("created_from", event.target.value)}
            />
          </div>
          <div className="filter-group">
            <span className="filter-label">Até:</span>
            <input
              type="date"
              aria-label="criado ate"
              value={filters.created_to}
              onChange={(event) => onFilterChange("created_to", event.target.value)}
            />
          </div>
          <button className="btn btn-subtle" type="submit" disabled={loading}>
            Aplicar filtros
          </button>
          <button className="btn btn-subtle" type="button" onClick={onClearFilters} disabled={loading}>
            Limpar
          </button>
          <a className="btn btn-accent" href="/?page=discover">
            Nova separacao
          </a>
        </form>

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

        {loading && <p className="inline-note">Carregando sessões...</p>}

        {!loading && sessions.length === 0 && (
          <section className="card empty-state" style={{ marginTop: 12 }}>
            <h3>Nenhuma sessão encontrada</h3>
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
                  <th>Sessão</th>
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
                      <td>{formatTrackLabel(session)}</td>
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

                          {session.status === "queued" && (
                            <button
                              className="btn btn-accent"
                              type="button"
                              onClick={() => onResumeDraft(session.session_id)}
                              disabled={rowIsBusy || loading}
                            >
                              Continuar
                            </button>
                          )}

                          {session.status !== "queued" &&
                            (isProcessingStatus(session.status) || session.status === "failed") && (
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

                          <button
                            className="btn btn-danger"
                            type="button"
                            onClick={() => onDelete(session.session_id, session.session_code)}
                            disabled={rowIsBusy || loading}
                          >
                            Excluir
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
                Página {page} de {totalPages} | {total} sessões
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
                  Próxima
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}

import { useMemo, useState } from "react";
import { connectJobSocket, createProcessJob, searchCandidates } from "./api";

const FINAL_STATES = new Set(["ready", "failed"]);

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [requiresSelection, setRequiresSelection] = useState(false);
  const [searchedQuery, setSearchedQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");

  const loading = searching || processing;

  const stemsList = useMemo(() => {
    if (!job?.stems) {
      return [];
    }
    return Object.entries(job.stems);
  }, [job]);

  const selectedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.source_id === selectedSourceId) || null,
    [candidates, selectedSourceId]
  );

  async function runSearch(queryValue = query.trim()) {
    setError("");

    if (queryValue.length < 3) {
      setError("Informe ao menos 3 caracteres na busca");
      return null;
    }

    try {
      setSearching(true);
      const response = await searchCandidates(queryValue, 5);
      const nextCandidates = response.candidates || [];

      setCandidates(nextCandidates);
      setSelectedSourceId(response.recommended_source_id || "");
      setRequiresSelection(Boolean(response.requires_selection));
      setSearchedQuery(queryValue);

      if (!nextCandidates.length) {
        setError("Nenhum resultado encontrado para a busca informada");
      }
      return response;
    } catch (err) {
      setError(err.message || "Falha ao buscar candidatos");
      return null;
    } finally {
      setSearching(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 3) {
      setError("Informe ao menos 3 caracteres na busca");
      return;
    }

    let activeCandidates = candidates;
    let activeSelectedSourceId = selectedSourceId;
    let activeRequiresSelection = requiresSelection;

    if (searchedQuery !== normalizedQuery || !candidates.length) {
      const searchResponse = await runSearch(normalizedQuery);
      if (!searchResponse) {
        return;
      }
      activeCandidates = searchResponse.candidates || [];
      activeSelectedSourceId = searchResponse.recommended_source_id || "";
      activeRequiresSelection = Boolean(searchResponse.requires_selection);
    }

    if (!activeCandidates.length) {
      setError("Nenhum candidato disponivel para processamento");
      return;
    }

    if (activeRequiresSelection && !activeSelectedSourceId) {
      setError("Selecione uma faixa antes de iniciar o processamento");
      return;
    }

    try {
      setProcessing(true);
      const response = await createProcessJob(normalizedQuery, activeSelectedSourceId || undefined);

      const socket = connectJobSocket(
        response.job_id,
        (payload) => {
          setJob(payload);
          if (FINAL_STATES.has(payload.state)) {
            socket.close();
            setProcessing(false);
          }
        },
        () => {
          setError("Falha na conexão de progresso em tempo real");
          setProcessing(false);
        }
      );
    } catch (err) {
      if (err.code === "AMBIGUOUS_QUERY") {
        setCandidates(err.candidates || []);
        setSelectedSourceId(err.recommendedSourceId || "");
        setRequiresSelection(true);
        setSearchedQuery(normalizedQuery);
        setError("Resultados ambiguos: selecione uma faixa para continuar");
      } else {
        setError(err.message || "Falha ao iniciar processamento");
      }
      setProcessing(false);
    }
  }

  return (
    <main className="app">
      <section className="hero">
        <h1>Music Analyzer MVP</h1>
        <p>
          Busque candidatos, selecione a melhor fonte e acompanhe o processamento
          de separacao em stems por WebSocket.
        </p>
      </section>

      <section className="card">
        <form className="form" onSubmit={handleSubmit}>
          <label className="label" htmlFor="query">
            Busca da faixa
          </label>

          <div className="input-row">
            <input
              id="query"
              type="text"
              placeholder="Ex: Daft Punk Get Lucky"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              disabled={processing}
            />
            <button type="button" className="btn-secondary" onClick={() => runSearch()} disabled={loading}>
              {searching ? "Buscando..." : "Buscar"}
            </button>
            <button type="submit" disabled={loading}>
              {processing ? "Processando..." : "Iniciar"}
            </button>
          </div>
        </form>

        {candidates.length > 0 && (
          <div className="results-wrap">
            <div className="results-header">
              <strong>Resultados da busca</strong>
              <span>
                {requiresSelection
                  ? "Selecao obrigatoria"
                  : "Melhor resultado pre-selecionado"}
              </span>
            </div>

            <ul className="results-list">
              {candidates.map((candidate) => {
                const isSelected = selectedSourceId === candidate.source_id;
                return (
                  <li
                    key={candidate.source_id}
                    className={`result-item ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedSourceId(candidate.source_id)}
                  >
                    <input
                      type="radio"
                      name="candidate"
                      checked={isSelected}
                      onChange={() => setSelectedSourceId(candidate.source_id)}
                    />

                    <div className="result-main">
                      <div className="result-title">{candidate.title}</div>
                      <div className="result-meta">
                        {candidate.artist} | {formatDuration(candidate.duration_seconds)} | {candidate.source}
                      </div>
                    </div>

                    <div className="result-side">
                      <span className="score-pill">match {candidate.score}%</span>
                      <a
                        href={candidate.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(event) => event.stopPropagation()}
                      >
                        Abrir fonte
                      </a>
                    </div>
                  </li>
                );
              })}
            </ul>

            {selectedCandidate && (
              <p className="selected-note">
                Selecionado: <strong>{selectedCandidate.title}</strong> ({selectedCandidate.score}% de match)
              </p>
            )}
          </div>
        )}

        {job && (
          <div className="progress-wrap">
            <div className="progress-label">
              <span>Job {job.job_id}</span>
              <strong>{job.progress}%</strong>
            </div>

            <div className="progress">
              <span style={{ width: `${job.progress}%` }} />
            </div>

            <div className="state">
              Estado: <strong>{job.state}</strong> | {job.message}
            </div>

            {job.selected_track && (
              <div className="state state-source">
                Fonte: <strong>{job.selected_track.title}</strong>
              </div>
            )}

            {stemsList.length > 0 && (
              <ul className="stems">
                {stemsList.map(([name, path]) => (
                  <li key={name}>
                    {name}: {path}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {error && <div className="error">{error}</div>}
      </section>
    </main>
  );
}

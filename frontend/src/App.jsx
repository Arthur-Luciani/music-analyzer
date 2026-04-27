import { useEffect, useMemo, useRef, useState } from "react";
import { connectJobSocket, createProcessJob, getStemAudioUrl, searchCandidates } from "./api";

const FINAL_STATES = new Set(["ready", "failed"]);
const PAGES = {
  discover: "discover",
  session: "session",
  workspace: "workspace",
  library: "library",
};

const STEM_ORDER = ["vocals", "drums", "bass", "other"];

function getFriendlySessionCode(jobId) {
  if (!jobId) {
    return "MX-000";
  }

  const seed = Array.from(jobId).reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const serial = (seed % 999) + 1;
  return `MX-${String(serial).padStart(3, "0")}`;
}

function getStateBadgeLabel(state) {
  if (state === "ready") {
    return "Pronta";
  }
  if (state === "failed") {
    return "Falhou";
  }
  if (state === "separating") {
    return "Separando";
  }
  if (state === "downloading") {
    return "Baixando";
  }
  return "Na fila";
}

function getStateBadgeClass(state) {
  if (state === "ready") {
    return "ready";
  }
  if (state === "failed") {
    return "failed";
  }
  if (state === "separating") {
    return "processing";
  }
  if (state === "downloading") {
    return "download";
  }
  return "processing";
}

function toFileName(pathLike) {
  if (!pathLike || typeof pathLike !== "string") {
    return "arquivo.wav";
  }
  const normalized = pathLike.replace(/\\/g, "/");
  const chunks = normalized.split("/");
  return chunks[chunks.length - 1] || "arquivo.wav";
}

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function formatBytes(sizeInBytes) {
  if (!sizeInBytes || sizeInBytes <= 0) {
    return "--";
  }

  const megaBytes = sizeInBytes / (1024 * 1024);
  return `${megaBytes.toFixed(1)} MB`;
}

export default function App() {
  const [currentPage, setCurrentPage] = useState(PAGES.discover);
  const [query, setQuery] = useState("");
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [stemSizes, setStemSizes] = useState({});
  const [mixLevels, setMixLevels] = useState({
    vocals: 84,
    drums: 72,
    bass: 65,
    other: 58,
    master: 78,
  });

  const loading = searching || processing;
  const stemAudioRefs = useRef({});
  const previewTimersRef = useRef({});

  const sessionCode = useMemo(() => {
    if (job?.session_code) {
      return job.session_code;
    }
    return getFriendlySessionCode(job?.job_id);
  }, [job?.session_code, job?.job_id]);

  const stemsList = useMemo(() => {
    if (!job?.stems) {
      return [];
    }
    const entries = Object.entries(job.stems);
    entries.sort((left, right) => STEM_ORDER.indexOf(left[0]) - STEM_ORDER.indexOf(right[0]));
    return entries;
  }, [job]);

  const selectedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.source_id === selectedSourceId) || null,
    [candidates, selectedSourceId]
  );

  const sessionStemPreview = useMemo(() => {
    const fallbackEnergy = {
      vocals: 92,
      drums: 74,
      bass: 66,
      other: 58,
    };

    const sizeValues = Object.values(stemSizes).filter((value) => Number.isFinite(value) && value > 0);
    const maxSize = sizeValues.length ? Math.max(...sizeValues) : 0;

    return stemsList.map(([stemName, stemPath]) => {
      const sizeInBytes = stemSizes[stemName] || 0;
      const normalizedEnergy = maxSize > 0 ? Math.round((sizeInBytes / maxSize) * 100) : fallbackEnergy[stemName] || 50;

      return {
        stemName,
        fileName: toFileName(stemPath),
        fileSizeLabel: formatBytes(sizeInBytes),
        energy: Math.max(12, normalizedEnergy),
        audioUrl: job?.job_id ? getStemAudioUrl(job.job_id, stemName) : "",
      };
    });
  }, [job?.job_id, stemSizes, stemsList]);

  const processingFacts = useMemo(() => {
    if (!job || !job.selected_track?.duration_seconds) {
      return null;
    }

    const duration = job.selected_track.duration_seconds;
    const progress = Math.max(0, Math.min(job.progress || 0, 100));
    const analyzedSeconds = Math.round((duration * progress) / 100);
    const remainingSeconds = Math.max(duration - analyzedSeconds, 0);

    return {
      analyzed: formatDuration(analyzedSeconds),
      total: formatDuration(duration),
      remaining: formatDuration(remainingSeconds),
    };
  }, [job]);

  useEffect(() => {
    return () => {
      Object.values(previewTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
      previewTimersRef.current = {};
    };
  }, []);

  useEffect(() => {
    if (!job?.job_id || job.state !== "ready" || !stemsList.length) {
      setStemSizes({});
      return;
    }

    let active = true;

    async function fetchStemSizes() {
      const entries = await Promise.all(
        stemsList.map(async ([stemName]) => {
          const url = getStemAudioUrl(job.job_id, stemName);
          try {
            const response = await fetch(url, { method: "HEAD" });
            if (!response.ok) {
              return [stemName, 0];
            }
            const header = response.headers.get("content-length") || "0";
            const parsed = Number(header);
            return [stemName, Number.isFinite(parsed) ? parsed : 0];
          } catch {
            return [stemName, 0];
          }
        })
      );

      if (active) {
        setStemSizes(Object.fromEntries(entries));
      }
    }

    fetchStemSizes();

    return () => {
      active = false;
    };
  }, [job?.job_id, job?.state, stemsList]);

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
      const recommendedSourceId = response.recommended_source_id || nextCandidates[0]?.source_id || "";

      setCandidates(nextCandidates);
      setSelectedSourceId(recommendedSourceId);
      setLastSearchQuery(queryValue);
      setJob(null);

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

    if (lastSearchQuery !== normalizedQuery || !candidates.length) {
      const searchResponse = await runSearch(normalizedQuery);
      if (!searchResponse) {
        return;
      }
      activeCandidates = searchResponse.candidates || [];
      activeSelectedSourceId =
        searchResponse.recommended_source_id || searchResponse.candidates?.[0]?.source_id || "";
    }

    if (!activeCandidates.length) {
      setError("Nenhum candidato disponivel para processamento");
      return;
    }

    if (!activeSelectedSourceId) {
      setError("Selecione uma faixa antes de iniciar o processamento");
      return;
    }

    try {
      setProcessing(true);
      const response = await createProcessJob(normalizedQuery, activeSelectedSourceId || undefined);
      setCurrentPage(PAGES.session);

      setJob({
        job_id: response.job_id,
        session_id: response.session_id,
        session_code: response.session_code,
        state: "queued",
        progress: 0,
        message: "Job criado. Aguardando processamento...",
      });

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
      setError(err.message || "Falha ao iniciar processamento");
      setProcessing(false);
    }
  }

  function updateMixLevel(name, value) {
    setMixLevels((prev) => ({
      ...prev,
      [name]: value,
    }));
  }

  function setStemAudioRef(stemName, node) {
    if (!node) {
      delete stemAudioRefs.current[stemName];
      return;
    }
    stemAudioRefs.current[stemName] = node;
  }

  function handlePlayStemPreview(stemName) {
    const audio = stemAudioRefs.current[stemName];
    if (!audio) {
      return;
    }

    if (previewTimersRef.current[stemName]) {
      window.clearTimeout(previewTimersRef.current[stemName]);
    }

    audio.currentTime = 0;
    audio.play().catch(() => {
      // Browsers may block autoplay in some contexts.
    });

    previewTimersRef.current[stemName] = window.setTimeout(() => {
      audio.pause();
      audio.currentTime = 0;
    }, 10000);
  }

  function renderDiscoverPage() {
    return (
      <div className="main-grid">
        <section className="card hero-card animate-up">
          <span className="kicker">Fluxo principal</span>
          <h1 className="hero-headline">Transforme uma musica em stems prontos para estudo ou criacao.</h1>
          <p className="hero-copy">
            Nova interface em React com foco em acao rapida: buscar, comparar fontes, selecionar e iniciar sessao
            com feedback continuo de progresso.
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

          {selectedCandidate && (
            <p className="inline-note">
              Sessao atual: <strong>{sessionCode}</strong> | <strong>{selectedCandidate.title}</strong>
            </p>
          )}

          {error && <p className="error-banner">{error}</p>}
        </section>

        <aside className="stack">
          <section className="card animate-up" style={{ animationDelay: "80ms" }}>
            <h3>Resumo rapido</h3>
            <div className="metric-grid" style={{ marginTop: 10 }}>
              <div className="metric">
                <div className="label">Tempo medio</div>
                <div className="value">2m 40s</div>
              </div>
              <div className="metric">
                <div className="label">Sucesso</div>
                <div className="value">98.2%</div>
              </div>
              <div className="metric">
                <div className="label">Fila atual</div>
                <div className="value">{processing ? "1 job" : "0 jobs"}</div>
              </div>
              <div className="metric">
                <div className="label">Modelo</div>
                <div className="value">htdemucs</div>
              </div>
            </div>
          </section>

          <section className="card animate-up" style={{ animationDelay: "150ms" }}>
            <h3>Sessoes recentes</h3>
            <div className="session-list" style={{ marginTop: 10 }}>
              <article className="session-item">
                <div>
                  <div className="title">MX-023 | Daft Punk - Get Lucky</div>
                  <div className="meta">Hoje, 14:02 | 4 stems exportados</div>
                </div>
                <span className="state ready">Pronta</span>
              </article>

              <article className="session-item">
                <div>
                  <div className="title">MX-022 | Billie Jean - Live Edit</div>
                  <div className="meta">Hoje, 13:44 | aguardando download</div>
                </div>
                <span className="state download">Baixando</span>
              </article>

              <article className="session-item">
                <div>
                  <div className="title">MX-021 | Shape of You - Acoustic</div>
                  <div className="meta">Hoje, 12:58 | ajuste de fonte</div>
                </div>
                <span className="state failed">Falhou</span>
              </article>
            </div>
          </section>
        </aside>
      </div>
    );
  }

  function renderSessionPage() {
    const hasJob = Boolean(job);
    const isReady = job?.state === "ready";
    const stateClass = getStateBadgeClass(job?.state);
    const stateLabel = getStateBadgeLabel(job?.state);

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
            <button className="btn btn-primary" type="button" onClick={() => setCurrentPage(PAGES.discover)}>
              Ir para Descobrir
            </button>
          </section>
        )}

        {hasJob && (
          <section className="card animate-up" style={{ marginTop: 12, animationDelay: "70ms" }}>
            <div className="timeline">
              <article
                className={`step ${job.state !== "queued" ? "done" : "live"}`}
              >
                <div className="name">1. Fonte validada</div>
                <div className="meta">Codigo {sessionCode}</div>
              </article>
              <article className={`step ${job.state === "downloading" || job.state === "separating" || job.state === "ready" ? "done" : ""}`}>
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
                    <div className="wave-bars" aria-hidden="true">
                      {new Array(16).fill(null).map((_, index) => (
                        <span
                          key={`bar-${index}`}
                          style={{
                            height: `${22 + ((index * 11) % 63)}%`,
                            "--delay": `${index * 0.04}s`,
                          }}
                        />
                      ))}
                    </div>

                    {processingFacts && (
                      <div className="analysis-facts">
                        <span className="fact-chip">
                          Analisado: {processingFacts.analyzed} / {processingFacts.total}
                        </span>
                        <span className="fact-chip">Restante estimado: {processingFacts.remaining}</span>
                      </div>
                    )}

                    <p className="inline-note">
                      {job.error ? `Erro: ${job.error}` : "Pipeline em execucao com atualizacao ao vivo."}
                    </p>
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
                            <span>{item.energy}% energia</span>
                          </div>

                          <div className="energy-track" aria-hidden="true">
                            <i style={{ width: `${item.energy}%` }} />
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
                      <div className="value short">{job.selected_track?.source || "youtube"}</div>
                    </div>
                  </div>
                </section>

                <section className="card">
                  <h3>Log de eventos</h3>
                  <div className="session-list" style={{ marginTop: 10 }}>
                    <article className="session-item">
                      <div>
                        <div className="title">Sessao iniciada</div>
                        <div className="meta">{job.selected_track?.title || "Fonte selecionada"}</div>
                      </div>
                      <span className="state ready">ok</span>
                    </article>
                    <article className="session-item">
                      <div>
                        <div className="title">Etapa atual</div>
                        <div className="meta">{job.message || "Aguardando"}</div>
                      </div>
                      <span className={`state ${stateClass}`}>{stateLabel}</span>
                    </article>
                  </div>
                </section>
              </div>
            </div>

            {job.state === "ready" && (
              <div className="session-actions">
                <button className="btn btn-primary" type="button" onClick={() => setCurrentPage(PAGES.workspace)}>
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

  function renderWorkspacePage() {
    const isReady = job?.state === "ready";
    const stemsToRender = stemsList.length
      ? stemsList
      : STEM_ORDER.map((stemName) => [stemName, `${stemName}.wav`]);

    return (
      <>
        <div className="page-title-row animate-up">
          <div>
            <h1>Workspace de stems {sessionCode !== "MX-000" ? `(${sessionCode})` : ""}</h1>
            <p>Controle de niveis por stem e organizacao para exportacao. Primeira fase de migracao no React.</p>
          </div>
          <span className={`state ${isReady ? "ready" : "processing"}`}>{isReady ? "Pronta" : "Aguardando"}</span>
        </div>

        {!job && (
          <section className="card empty-state" style={{ marginTop: 12 }}>
            <h3>Nenhuma sessao carregada</h3>
            <p>Inicie o processamento em Descobrir e acompanhe em Processamento.</p>
            <button className="btn btn-primary" type="button" onClick={() => setCurrentPage(PAGES.discover)}>
              Ir para Descobrir
            </button>
          </section>
        )}

        {job && (
          <div className="main-grid" style={{ marginTop: 14 }}>
            <section className="card animate-up">
              <h3>Mixer rapido</h3>
              <div className="channel-grid">
                {stemsToRender.map(([stemName]) => (
                  <article className="channel" key={stemName}>
                    <div className="channel-head">
                      <span className="channel-name">{stemName}</span>
                      <div className="channel-controls">
                        <button className="pill-btn" type="button">
                          Solo
                        </button>
                        <button className="pill-btn" type="button">
                          Mute
                        </button>
                      </div>
                    </div>
                    <div className="slider-wrap">
                      <input
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
                  </article>
                ))}
              </div>

              <section className="card wave-preview" style={{ marginTop: 12 }}>
                <h3>Master output</h3>
                <div className="slider-wrap" style={{ marginTop: 10 }}>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={mixLevels.master}
                    onChange={(event) => updateMixLevel("master", Number(event.target.value))}
                    disabled={!isReady}
                  />
                  <div className="slider-meta">
                    <span>Master gain</span>
                    <strong>{mixLevels.master}%</strong>
                  </div>
                </div>
              </section>
            </section>

            <aside className="stack animate-up" style={{ animationDelay: "90ms" }}>
              <section className="card">
                <h3>Exportacao</h3>
                <div className="session-list" style={{ marginTop: 10 }}>
                  <article className="session-item">
                    <div>
                      <div className="title">Preset Practice</div>
                      <div className="meta">Vocals +8, drums +4, bass -8</div>
                    </div>
                    <button className="btn btn-subtle" type="button">
                      Aplicar
                    </button>
                  </article>
                  <article className="session-item">
                    <div>
                      <div className="title">Preset Karaoke</div>
                      <div className="meta">Vocals 0, instrumental +10</div>
                    </div>
                    <button className="btn btn-subtle" type="button">
                      Aplicar
                    </button>
                  </article>
                </div>
                <div className="input-row" style={{ marginTop: 10 }}>
                  <button className="btn btn-primary" type="button" disabled={!isReady}>
                    Exportar mix
                  </button>
                  <button className="btn btn-accent" type="button" disabled={!isReady}>
                    Baixar stems
                  </button>
                </div>
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
                    {stemsToRender.map(([stemName, path]) => (
                      <tr key={stemName}>
                        <td>{stemName}</td>
                        <td>WAV</td>
                        <td>{toFileName(path)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="footer-note">Identidade de sessao na interface: {sessionCode}.</p>
              </section>
            </aside>
          </div>
        )}
      </>
    );
  }

  function renderLibraryPage() {
    return (
      <>
        <div className="page-title-row animate-up">
          <div>
            <h1>Biblioteca de sessoes</h1>
            <p>Historico inicial em React para retomar sessoes sem exposicao de identificadores tecnicos.</p>
          </div>
          <span className="state ready">Organizada</span>
        </div>

        <section className="card animate-up" style={{ marginTop: 12, animationDelay: "60ms" }}>
          <div className="search-filter">
            <input type="text" value="basket" readOnly aria-label="buscar na biblioteca" />
            <select aria-label="filtro de estado" defaultValue="Todos os estados">
              <option>Todos os estados</option>
              <option>Pronta</option>
              <option>Processando</option>
              <option>Falhou</option>
            </select>
            <button className="btn btn-subtle" type="button">
              Aplicar filtros
            </button>
          </div>

          <table className="library-table" aria-label="historico de sessoes" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Sessao</th>
                <th>Faixa</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {job && (
                <tr>
                  <td>{sessionCode}</td>
                  <td>{job.selected_track?.title || "Sessao atual"}</td>
                  <td>{getStateBadgeLabel(job.state)}</td>
                </tr>
              )}
              <tr>
                <td>MX-023</td>
                <td>Get Lucky - Topic Source</td>
                <td>Pronta</td>
              </tr>
              <tr>
                <td>MX-022</td>
                <td>Billie Jean - Live Edit</td>
                <td>Processando</td>
              </tr>
            </tbody>
          </table>
        </section>
      </>
    );
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <button className="brand" type="button" onClick={() => setCurrentPage(PAGES.discover)}>
          <span className="brand-badge">MX</span>
          <span className="brand-title">
            <strong>Music Analyzer</strong>
            <span>Studio Workspace</span>
          </span>
        </button>

        <nav className="nav-links" aria-label="Navegacao principal">
          <button
            type="button"
            className={`nav-link-btn ${currentPage === PAGES.discover ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.discover)}
          >
            Descobrir
          </button>
          <button
            type="button"
            className={`nav-link-btn ${currentPage === PAGES.session ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.session)}
          >
            Processamento
          </button>
          <button
            type="button"
            className={`nav-link-btn ${currentPage === PAGES.workspace ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.workspace)}
          >
            Workspace
          </button>
          <button
            type="button"
            className={`nav-link-btn ${currentPage === PAGES.library ? "active" : ""}`}
            onClick={() => setCurrentPage(PAGES.library)}
          >
            Biblioteca
          </button>
        </nav>

        <div className="topbar-right">
          <span className="user-chip mono">Sessao {sessionCode}</span>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => {
              setCurrentPage(PAGES.discover);
              setError("");
            }}
          >
            Nova sessao
          </button>
        </div>
      </header>

      {currentPage === PAGES.discover && renderDiscoverPage()}
      {currentPage === PAGES.session && renderSessionPage()}
      {currentPage === PAGES.workspace && renderWorkspacePage()}
      {currentPage === PAGES.library && renderLibraryPage()}
    </main>
  );
}

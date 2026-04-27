import { useEffect, useMemo, useRef, useState } from "react";
import {
  connectJobSocket,
  createExportJob,
  createProcessJob,
  duplicateSession,
  getExportFileUrl,
  getMixState,
  getSessionEvents,
  getSession,
  getStemAudioUrl,
  listExportJobs,
  listSessions,
  reprocessSession,
  searchCandidates,
  updateMixState,
} from "./api";
import { FINAL_STATES, PAGES, STEM_ORDER } from "./constants";
import { useSession } from "./context/SessionContext";
import DiscoverPage from "./pages/DiscoverPage";
import LibraryPage from "./pages/LibraryPage";
import SessionPage from "./pages/SessionPage";
import WorkspacePage from "./pages/WorkspacePage";
import {
  formatBytes,
  formatDuration,
  getFriendlySessionCode,
  getStateBadgeClass,
  getStateBadgeLabel,
  toFileName,
} from "./utils/formatters";

const LIBRARY_PAGE_SIZE = 8;
const PROCESSING_STATES = new Set(["queued", "downloading", "separating"]);
const EXPORT_ACTIVE_STATES = new Set(["queued", "processing"]);
const VALID_PAGE_SET = new Set(Object.values(PAGES));
const MIX_DB_MIN = -60;
const MIX_DB_MAX = 24;

const DEFAULT_MIX_LEVELS = {
  vocals: 84,
  drums: 72,
  bass: 65,
  other: 58,
  master: 78,
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function gainDbToPercent(gainValue) {
  const gain = Number.isFinite(gainValue) ? gainValue : 0;
  const normalized = ((clamp(gain, MIX_DB_MIN, MIX_DB_MAX) - MIX_DB_MIN) / (MIX_DB_MAX - MIX_DB_MIN)) * 100;
  return Math.round(normalized);
}

function percentToGainDb(percentValue) {
  const percent = Number.isFinite(percentValue) ? clamp(percentValue, 0, 100) : 0;
  const gain = MIX_DB_MIN + ((MIX_DB_MAX - MIX_DB_MIN) * percent) / 100;
  return Number(gain.toFixed(2));
}

function mixStateResponseToLevels(mixStatePayload) {
  const perStem = mixStatePayload?.per_stem || {};
  const nextLevels = { ...DEFAULT_MIX_LEVELS };

  STEM_ORDER.forEach((stemName) => {
    nextLevels[stemName] = gainDbToPercent(perStem?.[stemName]?.gain);
  });

  nextLevels.master = gainDbToPercent(mixStatePayload?.master_gain);
  return nextLevels;
}

function buildMixStateUpdatePayload(levels) {
  const perStem = {};

  STEM_ORDER.forEach((stemName) => {
    perStem[stemName] = {
      gain: percentToGainDb(levels?.[stemName] ?? DEFAULT_MIX_LEVELS[stemName]),
      pan: 0,
      mute: false,
      solo: false,
      send_fx: 0,
    };
  });

  return {
    per_stem: perStem,
    master_gain: percentToGainDb(levels?.master ?? DEFAULT_MIX_LEVELS.master),
  };
}

function serializeMixPayload(payload) {
  const normalizedPerStem = {};
  STEM_ORDER.forEach((stemName) => {
    const stemPayload = payload?.per_stem?.[stemName] || {};
    normalizedPerStem[stemName] = {
      gain: Number(stemPayload.gain ?? 0),
      pan: Number(stemPayload.pan ?? 0),
      mute: Boolean(stemPayload.mute),
      solo: Boolean(stemPayload.solo),
      send_fx: Number(stemPayload.send_fx ?? 0),
    };
  });

  return JSON.stringify({
    per_stem: normalizedPerStem,
    master_gain: Number(payload?.master_gain ?? 0),
  });
}

function toCreatedFromIso(dateValue) {
  if (!dateValue) {
    return undefined;
  }
  return `${dateValue}T00:00:00`;
}

function toCreatedToIso(dateValue) {
  if (!dateValue) {
    return undefined;
  }
  return `${dateValue}T23:59:59`;
}

function normalizeSessionDetail(session) {
  return {
    job_id: session.session_id,
    session_id: session.session_id,
    session_code: session.session_code,
    query: session.query,
    selected_track: session.selected_track || null,
    target_stems: session.target_stems || undefined,
    state: session.status,
    progress: session.progress ?? 0,
    message: session.message || "Sessao carregada",
    stems: session.stems || null,
    error: session.error || undefined,
    estimated_remaining_seconds: session.estimated_remaining_seconds ?? undefined,
    separation_device: session.separation_device ?? undefined,
    master_metrics: session.master_metrics ?? undefined,
  };
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
  const [sessionEvents, setSessionEvents] = useState([]);
  const [sessionEventsLoading, setSessionEventsLoading] = useState(false);
  const [sessionEventsError, setSessionEventsError] = useState("");
  const [stemSizes, setStemSizes] = useState({});
  const [mixLevels, setMixLevels] = useState(DEFAULT_MIX_LEVELS);
  const [mixStateLoading, setMixStateLoading] = useState(false);
  const [mixStateSaving, setMixStateSaving] = useState(false);
  const [mixStateError, setMixStateError] = useState("");
  const [exportJobs, setExportJobs] = useState([]);
  const [exportJobsLoading, setExportJobsLoading] = useState(false);
  const [exportJobsError, setExportJobsError] = useState("");
  const [exportActionLoading, setExportActionLoading] = useState("");
  const [exportActionMessage, setExportActionMessage] = useState("");
  const [libraryFilters, setLibraryFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [libraryAppliedFilters, setLibraryAppliedFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [libraryPage, setLibraryPage] = useState(1);
  const [libraryPayload, setLibraryPayload] = useState({
    items: [],
    total: 0,
    page: 1,
    page_size: LIBRARY_PAGE_SIZE,
  });
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState("");
  const [libraryActionLoading, setLibraryActionLoading] = useState("");
  const [libraryActionMessage, setLibraryActionMessage] = useState("");
  const [routeReady, setRouteReady] = useState(false);

  const { currentSession, setSessionFromPayload, clearSession } = useSession();

  const loading = searching || processing;
  const stemAudioRefs = useRef({});
  const previewTimersRef = useRef({});
  const jobSocketRef = useRef(null);
  const initialRouteAppliedRef = useRef(false);
  const loadedMixSessionRef = useRef("");
  const mixSaveTimerRef = useRef(null);
  const lastPersistedMixPayloadRef = useRef(serializeMixPayload(buildMixStateUpdatePayload(DEFAULT_MIX_LEVELS)));

  const libraryTotalPages = useMemo(() => {
    const total = libraryPayload.total || 0;
    const pageSize = libraryPayload.page_size || LIBRARY_PAGE_SIZE;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [libraryPayload.page_size, libraryPayload.total]);

  const sessionCode = useMemo(() => {
    if (currentSession.session_code) {
      return currentSession.session_code;
    }
    return getFriendlySessionCode(currentSession.job_id);
  }, [currentSession.job_id, currentSession.session_code]);

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
    const sizeValues = Object.values(stemSizes).filter((value) => Number.isFinite(value) && value > 0);
    const maxSize = sizeValues.length ? Math.max(...sizeValues) : 0;

    return stemsList.map(([stemName, stemPath]) => {
      const sizeInBytes = stemSizes[stemName] || 0;
      const normalizedEnergy = maxSize > 0 && sizeInBytes > 0 ? Math.round((sizeInBytes / maxSize) * 100) : null;

      return {
        stemName,
        fileName: toFileName(stemPath),
        fileSizeLabel: formatBytes(sizeInBytes),
        energy: Number.isFinite(normalizedEnergy) ? Math.max(12, normalizedEnergy) : null,
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

  function closeActiveJobSocket() {
    if (!jobSocketRef.current) {
      return;
    }
    jobSocketRef.current.close();
    jobSocketRef.current = null;
  }

  async function fetchSessionEventsForSession(sessionId, options = {}) {
    const { silent = false } = options;
    if (!sessionId) {
      return;
    }

    if (!silent) {
      setSessionEventsLoading(true);
    }
    setSessionEventsError("");

    try {
      const events = await getSessionEvents(sessionId);
      setSessionEvents(Array.isArray(events) ? events : []);
    } catch (err) {
      setSessionEventsError(err.message || "Falha ao carregar eventos da sessao");
    } finally {
      if (!silent) {
        setSessionEventsLoading(false);
      }
    }
  }

  async function fetchExportJobsForSession(sessionId, options = {}) {
    const { silent = false } = options;
    if (!sessionId) {
      return;
    }

    if (!silent) {
      setExportJobsLoading(true);
    }
    setExportJobsError("");

    try {
      const jobs = await listExportJobs(sessionId);
      setExportJobs(Array.isArray(jobs) ? jobs : []);
    } catch (err) {
      setExportJobsError(err.message || "Falha ao carregar exportacoes da sessao");
    } finally {
      if (!silent) {
        setExportJobsLoading(false);
      }
    }
  }

  async function createExportForSession(preset, formatName, options = {}) {
    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      setExportJobsError("Sessao indisponivel para criar exportacao");
      return;
    }

    if (job?.state !== "ready") {
      setExportJobsError("A exportacao exige sessao no estado pronta");
      return;
    }

    const actionKey = `${preset}:${formatName}`;
    setExportActionLoading(actionKey);
    setExportJobsError("");

    try {
      await createExportJob(sessionId, {
        preset,
        format: formatName,
        options,
      });

      setExportActionMessage(`Exportacao ${preset} iniciada.`);
      await fetchExportJobsForSession(sessionId, { silent: true });
    } catch (err) {
      setExportJobsError(err.message || "Falha ao iniciar exportacao");
    } finally {
      setExportActionLoading("");
    }
  }

  async function handleRetryExport(exportJob) {
    if (!exportJob) {
      return;
    }

    await createExportForSession(exportJob.preset || "study_mix", exportJob.format || "wav", {});
  }

  async function handleRefreshExports() {
    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      return;
    }

    await fetchExportJobsForSession(sessionId);
  }

  function applyHydratedSession(normalizedSession, targetPage) {
    setJob(normalizedSession);
    setSessionFromPayload(normalizedSession);
    setCurrentPage(targetPage);
    setError("");

    if (FINAL_STATES.has(normalizedSession.state)) {
      closeActiveJobSocket();
      setProcessing(false);
      return;
    }

    setProcessing(true);
    startJobSocket(normalizedSession.job_id);
  }

  async function hydrateSessionAndNavigate(sessionId, targetPage, options = {}) {
    const { loadingKey = "", clearLibraryError = false, onError } = options;

    if (!sessionId) {
      return;
    }

    if (loadingKey) {
      setLibraryActionLoading(loadingKey);
    }
    if (clearLibraryError) {
      setLibraryError("");
    }

    try {
      const detail = await getSession(sessionId);
      const normalized = normalizeSessionDetail(detail);
      applyHydratedSession(normalized, targetPage);
      await fetchSessionEventsForSession(normalized.session_id);
    } catch (err) {
      const message = err.message || "Falha ao abrir sessao selecionada";
      if (onError) {
        onError(message);
      } else {
        setError(message);
      }
    } finally {
      if (loadingKey) {
        setLibraryActionLoading("");
      }
    }
  }

  function startJobSocket(jobId) {
    if (!jobId) {
      return;
    }

    closeActiveJobSocket();
    jobSocketRef.current = connectJobSocket(
      jobId,
      (payload) => {
        setJob(payload);
        setSessionFromPayload(payload);
        if (FINAL_STATES.has(payload.state)) {
          fetchSessionEventsForSession(payload.session_id, { silent: true });
          closeActiveJobSocket();
          setProcessing(false);
        }
      },
      () => {
        setError("Falha na conexao de progresso em tempo real");
        setProcessing(false);
      }
    );
  }

  async function fetchLibrarySessions() {
    setLibraryLoading(true);
    setLibraryError("");

    try {
      const response = await listSessions({
        query: libraryAppliedFilters.query.trim() || undefined,
        status: libraryAppliedFilters.status || undefined,
        created_from: toCreatedFromIso(libraryAppliedFilters.created_from),
        created_to: toCreatedToIso(libraryAppliedFilters.created_to),
        page: libraryPage,
        page_size: LIBRARY_PAGE_SIZE,
      });
      setLibraryPayload(response);
    } catch (err) {
      setLibraryError(err.message || "Falha ao carregar sessoes da biblioteca");
    } finally {
      setLibraryLoading(false);
    }
  }

  async function openSessionFromLibrary(sessionId, targetPage) {
    await hydrateSessionAndNavigate(sessionId, targetPage, {
      loadingKey: `open:${sessionId}`,
      clearLibraryError: true,
      onError: (message) => setLibraryError(message),
    });
  }

  async function handleDuplicateFromLibrary(sessionId) {
    setLibraryActionLoading(`duplicate:${sessionId}`);
    setLibraryError("");

    try {
      const response = await duplicateSession(sessionId);
      setLibraryActionMessage(
        `Sessao ${response.session_code || "nova"} duplicada e processamento iniciado.`
      );
      await fetchLibrarySessions();
    } catch (err) {
      setLibraryError(err.message || "Falha ao duplicar sessao");
    } finally {
      setLibraryActionLoading("");
    }
  }

  async function handleReprocessFromLibrary(sessionId) {
    setLibraryActionLoading(`reprocess:${sessionId}`);
    setLibraryError("");

    try {
      const response = await reprocessSession(sessionId);
      setLibraryActionMessage(
        `Reprocessamento iniciado para a sessao ${response.session_code || "selecionada"}.`
      );
      await fetchLibrarySessions();
    } catch (err) {
      setLibraryError(err.message || "Falha ao reprocessar sessao");
    } finally {
      setLibraryActionLoading("");
    }
  }

  function handleApplyLibraryFilters() {
    setLibraryPage(1);
    setLibraryActionMessage("");
    setLibraryAppliedFilters({
      query: libraryFilters.query,
      status: libraryFilters.status,
      created_from: libraryFilters.created_from,
      created_to: libraryFilters.created_to,
    });
  }

  function handleClearLibraryFilters() {
    const empty = {
      query: "",
      status: "",
      created_from: "",
      created_to: "",
    };
    setLibraryFilters(empty);
    setLibraryAppliedFilters(empty);
    setLibraryPage(1);
    setLibraryActionMessage("");
  }

  useEffect(() => {
    return () => {
      Object.values(previewTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
      previewTimersRef.current = {};
      closeActiveJobSocket();
      if (mixSaveTimerRef.current) {
        window.clearTimeout(mixSaveTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (currentPage !== PAGES.library) {
      return;
    }
    fetchLibrarySessions();
  }, [currentPage, libraryAppliedFilters, libraryPage]);

  useEffect(() => {
    if (initialRouteAppliedRef.current) {
      return;
    }

    initialRouteAppliedRef.current = true;
    const params = new URLSearchParams(window.location.search);
    const requestedPage = params.get("page") || PAGES.discover;
    const targetPage = VALID_PAGE_SET.has(requestedPage) ? requestedPage : PAGES.discover;

    setCurrentPage(targetPage);
    setRouteReady(true);
  }, []);

  useEffect(() => {
    if (!routeReady) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    if (currentPage === PAGES.discover) {
      params.delete("page");
    } else {
      params.set("page", currentPage);
    }
    params.delete("session");

    const nextQuery = params.toString();
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
    const currentUrl = `${window.location.pathname}${window.location.search}`;

    if (nextUrl !== currentUrl) {
      window.history.replaceState({}, "", nextUrl);
    }
  }, [routeReady, currentPage]);

  useEffect(() => {
    if (currentPage !== PAGES.session) {
      return;
    }

    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      return;
    }

    fetchSessionEventsForSession(sessionId);

    if (FINAL_STATES.has(job?.state)) {
      return;
    }

    const intervalId = window.setInterval(() => {
      fetchSessionEventsForSession(sessionId, { silent: true });
    }, 5000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [currentPage, job?.session_id, job?.state, currentSession.session_id]);

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

  useEffect(() => {
    if (currentPage !== PAGES.workspace) {
      return;
    }

    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      return;
    }

    if (loadedMixSessionRef.current === sessionId) {
      return;
    }

    let active = true;
    setMixStateLoading(true);
    setMixStateError("");

    (async () => {
      try {
        const response = await getMixState(sessionId);
        if (!active) {
          return;
        }

        const levels = mixStateResponseToLevels(response);
        setMixLevels(levels);
        loadedMixSessionRef.current = sessionId;
        lastPersistedMixPayloadRef.current = serializeMixPayload(buildMixStateUpdatePayload(levels));
      } catch (err) {
        if (!active) {
          return;
        }

        setMixStateError(err.message || "Falha ao carregar mix-state da sessao");
        loadedMixSessionRef.current = sessionId;
      } finally {
        if (active) {
          setMixStateLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [currentPage, job?.session_id, currentSession.session_id]);

  useEffect(() => {
    if (currentPage !== PAGES.workspace) {
      return;
    }

    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId || mixStateLoading) {
      return;
    }

    const payload = buildMixStateUpdatePayload(mixLevels);
    const serialized = serializeMixPayload(payload);

    if (serialized === lastPersistedMixPayloadRef.current) {
      return;
    }

    if (mixSaveTimerRef.current) {
      window.clearTimeout(mixSaveTimerRef.current);
    }

    mixSaveTimerRef.current = window.setTimeout(async () => {
      setMixStateSaving(true);
      setMixStateError("");

      try {
        await updateMixState(sessionId, payload);
        lastPersistedMixPayloadRef.current = serialized;
      } catch (err) {
        setMixStateError(err.message || "Falha ao salvar mix-state da sessao");
      } finally {
        setMixStateSaving(false);
      }
    }, 650);

    return () => {
      if (mixSaveTimerRef.current) {
        window.clearTimeout(mixSaveTimerRef.current);
      }
    };
  }, [mixLevels, currentPage, job?.session_id, currentSession.session_id, mixStateLoading]);

  useEffect(() => {
    if (currentPage !== PAGES.workspace) {
      return;
    }

    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      setExportJobs([]);
      return;
    }

    fetchExportJobsForSession(sessionId);
  }, [currentPage, job?.session_id, currentSession.session_id]);

  useEffect(() => {
    if (currentPage !== PAGES.workspace) {
      return;
    }

    const sessionId = job?.session_id || currentSession.session_id;
    if (!sessionId) {
      return;
    }

    const hasActiveExport = exportJobs.some((exportJob) => EXPORT_ACTIVE_STATES.has(exportJob.state));
    if (!hasActiveExport) {
      return;
    }

    const intervalId = window.setInterval(() => {
      fetchExportJobsForSession(sessionId, { silent: true });
    }, 4000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [currentPage, job?.session_id, currentSession.session_id, exportJobs]);

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
      setSessionEvents([]);
      setSessionEventsError("");
      setMixLevels(DEFAULT_MIX_LEVELS);
      setMixStateError("");
      setExportJobs([]);
      setExportJobsError("");
      setExportActionMessage("");
      loadedMixSessionRef.current = "";
      lastPersistedMixPayloadRef.current = serializeMixPayload(buildMixStateUpdatePayload(DEFAULT_MIX_LEVELS));
      clearSession();

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
      setSessionEvents([]);
      setSessionEventsError("");
      setExportJobs([]);
      setExportJobsError("");
      setExportActionMessage("");
      const response = await createProcessJob(normalizedQuery, activeSelectedSourceId || undefined);
      setCurrentPage(PAGES.session);

      const nextJob = {
        job_id: response.job_id,
        session_id: response.session_id,
        session_code: response.session_code,
        state: "queued",
        progress: 0,
        message: "Job criado. Aguardando processamento...",
      };

      setJob(nextJob);
      setSessionFromPayload(nextJob);
      loadedMixSessionRef.current = "";
      startJobSocket(response.job_id);

      if (response.session_id) {
        fetchSessionEventsForSession(response.session_id, { silent: true });
      }
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
              closeActiveJobSocket();
              setProcessing(false);
              setJob(null);
              setSessionEvents([]);
              setSessionEventsError("");
              setMixLevels(DEFAULT_MIX_LEVELS);
              setMixStateError("");
              setExportJobs([]);
              setExportJobsError("");
              setExportActionMessage("");
              loadedMixSessionRef.current = "";
              lastPersistedMixPayloadRef.current = serializeMixPayload(buildMixStateUpdatePayload(DEFAULT_MIX_LEVELS));
              clearSession();
              setCurrentPage(PAGES.discover);
              setError("");
            }}
          >
            Nova sessao
          </button>
        </div>
      </header>

      {currentPage === PAGES.discover && (
        <DiscoverPage
          handleSubmit={handleSubmit}
          query={query}
          setQuery={setQuery}
          processing={processing}
          runSearch={runSearch}
          loading={loading}
          searching={searching}
          candidates={candidates}
          selectedSourceId={selectedSourceId}
          setSelectedSourceId={setSelectedSourceId}
          formatDuration={formatDuration}
          selectedCandidate={selectedCandidate}
          sessionCode={sessionCode}
          error={error}
        />
      )}

      {currentPage === PAGES.session && (
        <SessionPage
          job={job}
          sessionCode={sessionCode}
          error={error}
          processingFacts={processingFacts}
          sessionStemPreview={sessionStemPreview}
          setStemAudioRef={setStemAudioRef}
          handlePlayStemPreview={handlePlayStemPreview}
          sessionEvents={sessionEvents}
          sessionEventsLoading={sessionEventsLoading}
          sessionEventsError={sessionEventsError}
          getStateBadgeClass={getStateBadgeClass}
          getStateBadgeLabel={getStateBadgeLabel}
          onGoDiscover={() => setCurrentPage(PAGES.discover)}
          onGoWorkspace={() => setCurrentPage(PAGES.workspace)}
        />
      )}

      {currentPage === PAGES.workspace && (
        <WorkspacePage
          job={job}
          sessionCode={sessionCode}
          stemsList={stemsList}
          getStemAudioUrl={getStemAudioUrl}
          mixLevels={mixLevels}
          updateMixLevel={updateMixLevel}
          mixStateLoading={mixStateLoading}
          mixStateSaving={mixStateSaving}
          mixStateError={mixStateError}
          exportJobs={exportJobs}
          exportJobsLoading={exportJobsLoading}
          exportJobsError={exportJobsError}
          exportActionLoading={exportActionLoading}
          exportActionMessage={exportActionMessage}
          onCreateStudyMixExport={() => createExportForSession("study_mix", "wav")}
          onCreateStemsExport={() => createExportForSession("stems", "zip")}
          onCreateCustomExport={() =>
            createExportForSession("custom", "zip", {
              include_mix: true,
              include_stems: true,
            })
          }
          onRetryExport={handleRetryExport}
          onRefreshExports={handleRefreshExports}
          getExportFileUrl={getExportFileUrl}
          masterMetrics={job?.master_metrics || null}
          toFileName={toFileName}
          onGoDiscover={() => setCurrentPage(PAGES.discover)}
        />
      )}

      {currentPage === PAGES.library && (
        <LibraryPage
          sessions={libraryPayload.items || []}
          total={libraryPayload.total || 0}
          page={libraryPage}
          totalPages={libraryTotalPages}
          filters={libraryFilters}
          loading={libraryLoading}
          error={libraryError}
          actionLoading={libraryActionLoading}
          actionMessage={libraryActionMessage}
          getStateBadgeLabel={getStateBadgeLabel}
          getStateBadgeClass={getStateBadgeClass}
          onFilterChange={(name, value) =>
            setLibraryFilters((previous) => ({
              ...previous,
              [name]: value,
            }))
          }
          onApplyFilters={handleApplyLibraryFilters}
          onClearFilters={handleClearLibraryFilters}
          onRetry={fetchLibrarySessions}
          onPrevPage={() => setLibraryPage((previous) => Math.max(1, previous - 1))}
          onNextPage={() => setLibraryPage((previous) => Math.min(libraryTotalPages, previous + 1))}
          onOpenWorkspace={(sessionId) => openSessionFromLibrary(sessionId, PAGES.workspace)}
          onTrackSession={(sessionId) => openSessionFromLibrary(sessionId, PAGES.session)}
          onDuplicate={handleDuplicateFromLibrary}
          onReprocess={handleReprocessFromLibrary}
          isProcessingStatus={(status) => PROCESSING_STATES.has(status)}
        />
      )}
    </main>
  );
}

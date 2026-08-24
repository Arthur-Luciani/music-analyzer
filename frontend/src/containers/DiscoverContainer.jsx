import { useEffect, useState } from "react";
import { useDiscovery } from "../hooks/useDiscovery";
import { useMusicIdentity } from "../hooks/useMusicIdentity";
import DiscoverPage from "../pages/DiscoverPage";
import MusicIdentityStep from "../pages/MusicIdentityStep";
import { createDraftSession, deleteSession, getSession } from "../api";
import { useSession } from "../context/SessionContext";
import { useProcessingContext } from "../context/ProcessingContext";
import { formatDuration, getFriendlySessionCode } from "../utils/formatters";
import { PAGES } from "../constants";

export default function DiscoverContainer({ setCurrentPage, resumeSessionId, onResumeHandled, prefillQuery, onPrefillHandled }) {
  const discovery = useDiscovery();
  const identity = useMusicIdentity();
  const { currentSession } = useSession();
  const { startTracking } = useProcessingContext();
  const [submitting, setSubmitting] = useState(false);
  const [draftSession, setDraftSession] = useState(null); // { job_id, session_id, session_code }

  // Retomar um rascunho abandonado, vindo da Biblioteca — pula direto pro
  // step 3 usando o candidato que já foi selecionado quando o rascunho foi
  // criado (selected_track já está salvo na sessão desde então).
  useEffect(() => {
    if (!resumeSessionId) return;
    let cancelled = false;

    (async () => {
      try {
        const session = await getSession(resumeSessionId);
        if (cancelled) return;
        setDraftSession({
          job_id: session.job_id,
          session_id: session.session_id,
          session_code: session.session_code,
        });
        identity.initFrom(session.selected_track);
        onResumeHandled?.();
      } catch (err) {
        if (cancelled) return;
        discovery.setError(err.message || "Não foi possível retomar o rascunho");
        onResumeHandled?.();
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeSessionId]);

  // Vindo do Catálogo, com um MIDI sem sessão vinculada — pré-preenche e já
  // dispara a busca pra economizar um passo do usuário.
  useEffect(() => {
    if (!prefillQuery) return;
    discovery.setQuery(prefillQuery);
    discovery.runSearch(prefillQuery);
    onPrefillHandled?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillQuery]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    discovery.setError("");

    const normalizedQuery = discovery.query.trim();
    if (normalizedQuery.length < 3) {
      discovery.setError("Informe ao menos 3 caracteres na busca");
      return;
    }

    let activeCandidates = discovery.candidates;
    let activeSelectedSourceId = discovery.selectedSourceId;

    // Re-search if query changed or candidates are empty
    if (discovery.lastSearchQuery !== normalizedQuery || !discovery.candidates.length) {
      const searchResponse = await discovery.runSearch(normalizedQuery);
      if (!searchResponse) return;
      activeCandidates = searchResponse.candidates || [];
      activeSelectedSourceId =
        searchResponse.recommended_source_id || searchResponse.candidates?.[0]?.source_id || "";
    }

    if (!activeCandidates.length) {
      discovery.setError("Nenhum candidato disponivel para processamento");
      return;
    }

    if (!activeSelectedSourceId) {
      discovery.setError("Selecione uma faixa antes de iniciar o processamento");
      return;
    }

    try {
      setSubmitting(true);
      const response = await createDraftSession(normalizedQuery, activeSelectedSourceId);
      const pickedCandidate = activeCandidates.find((c) => c.source_id === activeSelectedSourceId) || null;
      setDraftSession(response);
      identity.initFrom(pickedCandidate);
    } catch (err) {
      discovery.setError(err.message || "Falha ao iniciar sessão");
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmIdentity = async () => {
    if (!draftSession) return;
    const confirmed = await identity.confirm(draftSession.session_id);
    if (!confirmed) return;

    startTracking(draftSession.job_id);
    setCurrentPage(PAGES.library);
  };

  const handleDiscardDraft = async () => {
    if (!draftSession) return;
    try {
      await deleteSession(draftSession.session_id);
    } catch {
      // Se a exclusão falhar, o usuário ainda pode descartar depois pela
      // Biblioteca — não bloqueia a navegação de volta.
    }
    setDraftSession(null);
  };

  if (draftSession) {
    return (
      <MusicIdentityStep
        sessionCode={draftSession.session_code}
        artistText={identity.artistText}
        titleText={identity.titleText}
        setTitleText={identity.setTitleText}
        onArtistTextChange={identity.handleArtistTextChange}
        selectedArtistId={identity.selectedArtistId}
        suggestions={identity.suggestions}
        resolving={identity.resolving}
        pickSuggestion={identity.pickSuggestion}
        confirming={identity.confirming}
        error={identity.error}
        onConfirm={handleConfirmIdentity}
        onBack={handleDiscardDraft}
      />
    );
  }

  const sessionCode = currentSession.session_code || getFriendlySessionCode(currentSession.job_id);
  const loading = discovery.searching || submitting;

  return (
    <DiscoverPage
      {...discovery}
      handleSubmit={handleSubmit}
      formatDuration={formatDuration}
      sessionCode={sessionCode}
      loading={loading}
      processing={submitting}
    />
  );
}

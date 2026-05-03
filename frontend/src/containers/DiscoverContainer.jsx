import { useState } from "react";
import { useDiscovery } from "../hooks/useDiscovery";
import DiscoverPage from "../pages/DiscoverPage";
import { createProcessJob } from "../api";
import { useSession } from "../context/SessionContext";
import { useProcessingContext } from "../context/ProcessingContext";
import { formatDuration, getFriendlySessionCode } from "../utils/formatters";
import { PAGES } from "../constants";

export default function DiscoverContainer({ setCurrentPage }) {
  const discovery = useDiscovery();
  const { currentSession } = useSession();
  const { startTracking } = useProcessingContext();
  const [submitting, setSubmitting] = useState(false);

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
      const response = await createProcessJob(normalizedQuery, activeSelectedSourceId);

      // Start background tracking and go to library
      startTracking(response.job_id);
      setCurrentPage(PAGES.library);
    } catch (err) {
      discovery.setError(err.message || "Falha ao iniciar processamento");
    } finally {
      setSubmitting(false);
    }
  };

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

import { useEffect, useCallback } from "react";
import { useLibrary } from "../hooks/useLibrary";
import { useSession } from "../context/SessionContext";
import { useProcessingContext } from "../context/ProcessingContext";
import LibraryPage from "../pages/LibraryPage";
import { PAGES } from "../constants";
import { formatDuration, getStateBadgeClass, getStateBadgeLabel } from "../utils/formatters";

export default function LibraryContainer({ setCurrentPage }) {
  const library = useLibrary();
  const { hydratSessionAndNavigate } = useSession();
  const { startTracking } = useProcessingContext();

  useEffect(() => {
    library.fetchSessions();
  }, [library.page, library.appliedFilters, library.fetchSessions]);

  const { job } = useProcessingContext();

  // 1. Sincronização imediata com o job que está sendo acompanhado
  useEffect(() => {
    if (job && job.state) {
      library.setPayload((prev) => {
        const currentItems = prev.items || [];
        const hasChange = currentItems.some(
          (s) => s.session_id === job.job_id && s.status !== job.state
        );

        if (!hasChange) return prev;

        console.log(`[LibraryContainer] Atualizando status local para ${job.job_id}: ${job.state}`);
        return {
          ...prev,
          items: currentItems.map((s) =>
            s.session_id === job.job_id ? { ...s, status: job.state } : s
          ),
        };
      });
    }
  }, [job, library.setPayload]);

  // 2. Polling de fundo se houver sessões processando (para manter tudo atualizado)
  useEffect(() => {
    const sessions = library.payload.items || [];
    const hasProcessing = sessions.some((s) =>
      ["queued", "downloading", "separating"].includes(s.status)
    );

    if (hasProcessing && !library.loading) {
      const timer = setTimeout(() => {
        console.log("[LibraryContainer] Executando refresh de fundo...");
        library.fetchSessions(true); // background = true
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [library.payload.items, library.loading, library.fetchSessions]);

  const handleOpenWorkspace = async (sessionId) => {
    await hydratSessionAndNavigate(sessionId);
    setCurrentPage(PAGES.workspace);
  };

  const handleTrackSession = async (sessionId) => {
    startTracking(sessionId);
  };

  const isProcessingStatus = useCallback((status) => {
    return status === "queued" || status === "downloading" || status === "separating";
  }, []);

  return (
    <LibraryPage
      sessions={library.payload.items || []}
      total={library.payload.total || 0}
      page={library.page}
      totalPages={library.totalPages}
      filters={library.filters}
      loading={library.loading}
      error={library.error}
      actionLoading={library.actionLoading}
      actionMessage={library.actionMessage}
      getStateBadgeLabel={getStateBadgeLabel}
      getStateBadgeClass={getStateBadgeClass}
      onFilterChange={(key, value) => library.setFilters((prev) => ({ ...prev, [key]: value }))}
      onApplyFilters={() => library.setAppliedFilters(library.filters)}
      onClearFilters={() => {
        const empty = { query: "", status: "", created_from: "", created_to: "" };
        library.setFilters(empty);
        library.setAppliedFilters(empty);
      }}
      onRetry={library.fetchSessions}
      onPrevPage={() => library.setPage((p) => Math.max(1, p - 1))}
      onNextPage={() => library.setPage((p) => Math.min(library.totalPages, p + 1))}
      onOpenWorkspace={handleOpenWorkspace}
      onTrackSession={handleTrackSession}
      onDuplicate={library.handleDuplicate}
      onReprocess={library.handleReprocess}
      onDelete={library.handleDelete}
      isProcessingStatus={isProcessingStatus}
    />
  );
}

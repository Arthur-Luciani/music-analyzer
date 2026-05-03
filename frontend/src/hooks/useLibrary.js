import { useState } from "react";
import { listSessions, duplicateSession, reprocessSession, deleteSession } from "../api";

const LIBRARY_PAGE_SIZE = 8;

export function useLibrary() {
  const [filters, setFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [appliedFilters, setAppliedFilters] = useState({
    query: "",
    status: "",
    created_from: "",
    created_to: "",
  });
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState({ items: [], total: 0, page: 1, page_size: LIBRARY_PAGE_SIZE });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const fetchSessions = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await listSessions({
        query: appliedFilters.query.trim() || undefined,
        status: appliedFilters.status || undefined,
        page,
        page_size: LIBRARY_PAGE_SIZE,
      });
      setPayload(response);
    } catch (err) {
      setError(err.message || "Falha ao carregar sessões");
    } finally {
      setLoading(false);
    }
  };

  const handleDuplicate = async (sessionId) => {
    setActionLoading(`duplicate:${sessionId}`);
    setError("");

    try {
      await duplicateSession(sessionId);
      setActionMessage(`Sessão duplicada`);
      await fetchSessions();
    } catch (err) {
      setError(err.message || "Falha ao duplicar");
    } finally {
      setActionLoading("");
    }
  };

  const handleReprocess = async (sessionId) => {
    setActionLoading(`reprocess:${sessionId}`);
    setError("");

    try {
      await reprocessSession(sessionId);
      setActionMessage(`Reprocessamento iniciado`);
      await fetchSessions();
    } catch (err) {
      setError(err.message || "Falha ao reprocessar");
    } finally {
      setActionLoading("");
    }
  };

  const handleDelete = async (sessionId, sessionCode) => {
    const label = sessionCode ? `a sessão ${sessionCode}` : "esta sessão";
    if (!window.confirm(`Tem certeza que deseja excluir ${label}? Esta ação é irreversível e apagará os stems do disco.`)) {
      return;
    }

    setActionLoading(`delete:${sessionId}`);
    setError("");

    try {
      await deleteSession(sessionId);
      setActionMessage(`Sessão excluída`);
      // If we deleted the last item on this page, go back one page
      setPage((prev) => {
        const currentItems = payload.items?.length || 0;
        return currentItems === 1 && prev > 1 ? prev - 1 : prev;
      });
      await fetchSessions();
    } catch (err) {
      setError(err.message || "Falha ao excluir sessão");
    } finally {
      setActionLoading("");
    }
  };

  const totalPages = Math.max(
    1,
    Math.ceil((payload.total || 0) / (payload.page_size || LIBRARY_PAGE_SIZE))
  );

  return {
    filters,
    setFilters,
    appliedFilters,
    setAppliedFilters,
    page,
    setPage,
    payload,
    loading,
    error,
    actionLoading,
    actionMessage,
    totalPages,
    fetchSessions,
    handleDuplicate,
    handleReprocess,
    handleDelete,
  };
}

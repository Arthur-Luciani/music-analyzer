import { useState } from "react";
import { searchCandidates } from "../api";

export function useDiscovery() {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  const runSearch = async (queryValue = query.trim()) => {
    setError("");

    if (queryValue.length < 3) {
      setError("Informe ao menos 3 caracteres na busca");
      return null;
    }

    try {
      setSearching(true);
      const response = await searchCandidates(queryValue, 5);
      const nextCandidates = response.candidates || [];
      const recommendedSourceId =
        response.recommended_source_id || nextCandidates[0]?.source_id || "";

      setCandidates(nextCandidates);
      setSelectedSourceId(recommendedSourceId);
      setLastSearchQuery(queryValue);

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
  };

  const selectedCandidate = candidates.find(
    (c) => c.source_id === selectedSourceId
  ) || null;

  return {
    query,
    setQuery,
    candidates,
    selectedSourceId,
    setSelectedSourceId,
    searching,
    error,
    setError, // Note: Added setError to be able to set errors from container
    runSearch,
    selectedCandidate,
    lastSearchQuery,
  };
}

import { useCallback, useRef, useState } from "react";
import { confirmSession, resolveArtistCandidates, saveMusicIdentity } from "../api";

const SUGGESTION_DEBOUNCE_MS = 350;

export function useMusicIdentity() {
  const [artistText, setArtistText] = useState("");
  const [titleText, setTitleText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [selectedArtistId, setSelectedArtistId] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [resolving, setResolving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef(null);

  const initFrom = useCallback((candidate) => {
    setArtistText(candidate?.artist || "");
    setTitleText(candidate?.title || "");
    setSourceUrl(candidate?.url || "");
    setSelectedArtistId(null);
    setSuggestions([]);
    setError("");
  }, []);

  const handleArtistTextChange = useCallback((value) => {
    setArtistText(value);
    setSelectedArtistId(null); // editar o texto invalida a sugestão selecionada antes

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (value.trim().length < 2) {
      setSuggestions([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      try {
        setResolving(true);
        const results = await resolveArtistCandidates(value.trim());
        setSuggestions(results || []);
      } catch {
        // Preview é best-effort — uma falha aqui não deve travar o wizard.
        setSuggestions([]);
      } finally {
        setResolving(false);
      }
    }, SUGGESTION_DEBOUNCE_MS);
  }, []);

  const pickSuggestion = useCallback((candidate) => {
    setArtistText(candidate.name);
    setSelectedArtistId(candidate.id);
    setSuggestions([]);
  }, []);

  const confirm = useCallback(
    async (sessionId) => {
      setError("");

      if (!artistText.trim() || !titleText.trim()) {
        setError("Informe artista e música antes de confirmar");
        return false;
      }

      try {
        setConfirming(true);
        await saveMusicIdentity(sessionId, {
          artist_text: artistText.trim(),
          title_text: titleText.trim(),
          artist_id: selectedArtistId,
          source_url: sourceUrl || null,
        });
        await confirmSession(sessionId);
        return true;
      } catch (err) {
        setError(err.message || "Falha ao confirmar sessão");
        return false;
      } finally {
        setConfirming(false);
      }
    },
    [artistText, titleText, selectedArtistId, sourceUrl]
  );

  return {
    artistText,
    titleText,
    setTitleText,
    sourceUrl,
    selectedArtistId,
    suggestions,
    resolving,
    confirming,
    error,
    setError,
    initFrom,
    handleArtistTextChange,
    pickSuggestion,
    confirm,
  };
}

import { useState, useCallback } from "react";
import {
  listMarketArtists,
  getMarketArtist,
  updateMarketArtist,
  deleteMarketArtist,
  listMarketTracks,
  getMarketTrack,
  updateMarketTrack,
  deleteMarketTrack,
  deleteMarketMidiFile,
} from "../api";
import { useDialog } from "../context/DialogContext";

const PAGE_SIZE = 20;

export function useMarketCatalog() {
  const { confirm } = useDialog();
  const [view, setView] = useState("artists"); // "artists" | "artistDetail" | "trackDetail"

  const [artistQuery, setArtistQuery] = useState("");
  const [appliedArtistQuery, setAppliedArtistQuery] = useState("");
  const [artistPage, setArtistPage] = useState(1);
  const [artistPayload, setArtistPayload] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [artistsLoading, setArtistsLoading] = useState(false);
  const [artistsError, setArtistsError] = useState("");

  const [selectedArtistId, setSelectedArtistId] = useState(null);
  const [artistDetail, setArtistDetail] = useState(null);
  const [artistDetailLoading, setArtistDetailLoading] = useState(false);
  const [artistDetailError, setArtistDetailError] = useState("");

  const [trackPage, setTrackPage] = useState(1);
  const [trackPayload, setTrackPayload] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [tracksLoading, setTracksLoading] = useState(false);
  const [tracksError, setTracksError] = useState("");

  const [selectedTrackId, setSelectedTrackId] = useState(null);
  const [trackDetail, setTrackDetail] = useState(null);
  const [trackDetailLoading, setTrackDetailLoading] = useState(false);
  const [trackDetailError, setTrackDetailError] = useState("");

  const [actionLoading, setActionLoading] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const fetchArtists = useCallback(async () => {
    setArtistsLoading(true);
    setArtistsError("");
    try {
      const response = await listMarketArtists({
        query: appliedArtistQuery.trim() || undefined,
        page: artistPage,
        page_size: PAGE_SIZE,
      });
      setArtistPayload(response);
    } catch (err) {
      setArtistsError(err.message || "Falha ao carregar artistas");
    } finally {
      setArtistsLoading(false);
    }
  }, [appliedArtistQuery, artistPage]);

  const fetchArtistDetail = useCallback(async (artistId) => {
    setSelectedArtistId(artistId);
    setView("artistDetail");
    setTrackPage(1);
    setArtistDetailLoading(true);
    setArtistDetailError("");
    try {
      const detail = await getMarketArtist(artistId);
      setArtistDetail(detail);
    } catch (err) {
      setArtistDetailError(err.message || "Falha ao carregar artista");
    } finally {
      setArtistDetailLoading(false);
    }
  }, []);

  const fetchTracks = useCallback(async () => {
    if (selectedArtistId == null) return;
    setTracksLoading(true);
    setTracksError("");
    try {
      const response = await listMarketTracks({ artist_id: selectedArtistId, page: trackPage, page_size: PAGE_SIZE });
      setTrackPayload(response);
    } catch (err) {
      setTracksError(err.message || "Falha ao carregar músicas");
    } finally {
      setTracksLoading(false);
    }
  }, [selectedArtistId, trackPage]);

  const fetchTrackDetail = useCallback(async (trackId) => {
    setSelectedTrackId(trackId);
    setView("trackDetail");
    setTrackDetailLoading(true);
    setTrackDetailError("");
    try {
      const detail = await getMarketTrack(trackId);
      setTrackDetail(detail);
    } catch (err) {
      setTrackDetailError(err.message || "Falha ao carregar música");
    } finally {
      setTrackDetailLoading(false);
    }
  }, []);

  const handleRenameArtist = async (artistId, newName) => {
    setActionLoading(`rename-artist:${artistId}`);
    setArtistsError("");
    try {
      await updateMarketArtist(artistId, { name: newName });
      setActionMessage("Artista renomeado");
      await fetchArtists();
      if (selectedArtistId === artistId) {
        await fetchArtistDetail(artistId);
      }
    } catch (err) {
      setArtistsError(err.message || "Falha ao renomear artista");
    } finally {
      setActionLoading("");
    }
  };

  const handleDeleteArtist = async (artistId, artistName) => {
    const confirmed = await confirm(
      `Tem certeza que deseja excluir "${artistName}"? Isso apaga também todas as músicas e arquivos MIDI dele. Esta ação é irreversível.`,
      { title: "Excluir artista", confirmLabel: "Excluir", danger: true }
    );
    if (!confirmed) {
      return;
    }

    setActionLoading(`delete-artist:${artistId}`);
    setArtistsError("");
    try {
      await deleteMarketArtist(artistId);
      setActionMessage("Artista excluído");
      if (selectedArtistId === artistId) {
        setView("artists");
        setSelectedArtistId(null);
        setArtistDetail(null);
      }
      await fetchArtists();
    } catch (err) {
      setArtistsError(err.message || "Falha ao excluir artista");
    } finally {
      setActionLoading("");
    }
  };

  const handleRenameTrack = async (trackId, updates) => {
    setActionLoading(`update-track:${trackId}`);
    setTracksError("");
    try {
      await updateMarketTrack(trackId, updates);
      setActionMessage("Música atualizada");
      await fetchTracks();
      if (selectedTrackId === trackId) {
        await fetchTrackDetail(trackId);
      }
    } catch (err) {
      setTracksError(err.message || "Falha ao atualizar música");
    } finally {
      setActionLoading("");
    }
  };

  const handleDeleteTrack = async (trackId, trackTitle) => {
    const confirmed = await confirm(
      `Tem certeza que deseja excluir "${trackTitle}"? Isso apaga também os arquivos MIDI dela. Esta ação é irreversível.`,
      { title: "Excluir música", confirmLabel: "Excluir", danger: true }
    );
    if (!confirmed) {
      return;
    }

    setActionLoading(`delete-track:${trackId}`);
    setTracksError("");
    try {
      await deleteMarketTrack(trackId);
      setActionMessage("Música excluída");
      if (selectedTrackId === trackId) {
        setView("artistDetail");
        setSelectedTrackId(null);
        setTrackDetail(null);
      }
      await fetchTracks();
    } catch (err) {
      setTracksError(err.message || "Falha ao excluir música");
    } finally {
      setActionLoading("");
    }
  };

  const handleDeleteMidiFile = async (fileId, relativePath) => {
    const confirmed = await confirm(`Tem certeza que deseja excluir o arquivo "${relativePath}"? Esta ação é irreversível.`, {
      title: "Excluir arquivo MIDI",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!confirmed) {
      return;
    }

    setActionLoading(`delete-file:${fileId}`);
    setTrackDetailError("");
    try {
      await deleteMarketMidiFile(fileId);
      setActionMessage("Arquivo MIDI excluído");
      if (selectedTrackId != null) {
        await fetchTrackDetail(selectedTrackId);
      }
    } catch (err) {
      setTrackDetailError(err.message || "Falha ao excluir arquivo MIDI");
    } finally {
      setActionLoading("");
    }
  };

  const goBackToArtists = () => {
    setView("artists");
    setSelectedArtistId(null);
    setArtistDetail(null);
    setSelectedTrackId(null);
    setTrackDetail(null);
  };

  const goBackToArtistDetail = () => {
    setView("artistDetail");
    setSelectedTrackId(null);
    setTrackDetail(null);
  };

  const totalArtistPages = Math.max(1, Math.ceil((artistPayload.total || 0) / (artistPayload.page_size || PAGE_SIZE)));
  const totalTrackPages = Math.max(1, Math.ceil((trackPayload.total || 0) / (trackPayload.page_size || PAGE_SIZE)));

  return {
    view,
    setView,
    artistQuery,
    setArtistQuery,
    appliedArtistQuery,
    setAppliedArtistQuery,
    artistPage,
    setArtistPage,
    artistPayload,
    artistsLoading,
    artistsError,
    totalArtistPages,
    fetchArtists,

    selectedArtistId,
    artistDetail,
    artistDetailLoading,
    artistDetailError,
    fetchArtistDetail,

    trackPage,
    setTrackPage,
    trackPayload,
    tracksLoading,
    tracksError,
    totalTrackPages,
    fetchTracks,

    selectedTrackId,
    trackDetail,
    trackDetailLoading,
    trackDetailError,
    fetchTrackDetail,

    actionLoading,
    actionMessage,

    handleRenameArtist,
    handleDeleteArtist,
    handleRenameTrack,
    handleDeleteTrack,
    handleDeleteMidiFile,
    goBackToArtists,
    goBackToArtistDetail,
  };
}

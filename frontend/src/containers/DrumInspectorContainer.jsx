import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import WaveSurfer from "wavesurfer.js";
import DrumInspectorPage from "../pages/DrumInspectorPage";
import { getStemAudioUrl, getMusicIdentity } from "../api";
import { useWebAudioMixer } from "../hooks/useWebAudioMixer";
import { useMusicIdentity } from "../hooks/useMusicIdentity";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";

export default function DrumInspectorContainer({ session, workspace, onBack }) {
  const {
    drumAnalysis,
    saveDrumCorrectionsAction,
    mixLevels,
    soloStem,
    mutedStems,
    panLevels,
    marketMidiStatus,
  } = workspace;
  
  const [wavesurfer, setWavesurfer] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [editedHits, setEditedHits] = useState([]);
  const [selectedHitIndex, setSelectedHitIndex] = useState(null);
  const [saving, setSaving] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(20);
  const [identityEditOpen, setIdentityEditOpen] = useState(false);
  const identity = useMusicIdentity();

  const containerRef = useRef(null);
  const scrollRef = useRef(null);
  const currentTimeRef = useRef(0);
  const audioElementsRef = useRef({});

  // Mixer Setup
  const stemNames = useMemo(() => {
    return Object.keys(mixLevels || {}).filter(name => name !== 'master');
  }, [mixLevels]);

  const { initAudioContext } = useWebAudioMixer({
    stemNames,
    audioElementsRef,
    mixLevels: mixLevels || {},
    panLevels: panLevels || {},
    mutedStems: mutedStems || {},
    soloStem: soloStem || null,
    isPlaying,
  });

  // Sincroniza o ref sempre que a prop mudar
  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  // Forçar atualização da análise ao entrar no Inspetor
  useEffect(() => {
    if (session?.session_id) {
      workspace.fetchDrumAnalysis(session.session_id);
    }
  }, [session?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize hits from analysis
  useEffect(() => {
    if (drumAnalysis?.hits) {
      setEditedHits([...drumAnalysis.hits]);
    }
  }, [drumAnalysis]);

  // Initialize Wavesurfer (VISUAL ONLY)
  useEffect(() => {
    if (!containerRef.current || !session?.job_id) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#434b56",
      progressColor: "#c18a3a",
      cursorColor: "transparent",
      barWidth: 2,
      barGap: 1,
      height: 150,
      normalize: true,
      hideScrollbar: true,
      responsive: true,
      fillParent: true,
      interact: false,
      // O wavesurfer tem seu próprio auto-scroll/auto-center interno (ligado
      // por padrão) que compete com o scroll manual que já sincronizamos em
      // DrumInspectorPage.jsx — os dois brigando pelo mesmo espaço causava o
      // cursor indo "para trás" com o tempo. Desligamos o dele, já que o
      // nosso próprio loop já mantém waveform e grid sincronizados.
      autoScroll: false,
      autoCenter: false,
    });

    const audioUrl = getStemAudioUrl(session.job_id, "drums");
    ws.load(audioUrl);
    ws.setMuted(true);

    ws.on("ready", () => {
      setIsReady(true);
      setWavesurfer(ws);
    });

    return () => ws.destroy();
  }, [session?.job_id]);

  // Sync Timer Loop (High Performance)
  useEffect(() => {
    let rafId;
    const sync = () => {
      const activeAudio = audioElementsRef.current["drums"];
      if (activeAudio && isPlaying) {
        const time = activeAudio.currentTime;
        setCurrentTime(time);
        if (wavesurfer) wavesurfer.setTime(time);
        rafId = requestAnimationFrame(sync);
      }
    };
    if (isPlaying) rafId = requestAnimationFrame(sync);
    return () => cancelAnimationFrame(rafId);
  }, [isPlaying, wavesurfer]);

  // Handle Playback Speed and Zoom
  useEffect(() => {
    if (wavesurfer) {
      wavesurfer.setPlaybackRate(playbackSpeed);
    }
  }, [wavesurfer, playbackSpeed]);

  useEffect(() => {
    if (wavesurfer) {
      wavesurfer.zoom(zoomLevel);
    }
  }, [wavesurfer, zoomLevel]);

  // Auto-select nearest hit when seeking/playing
  useEffect(() => {
    if (!isReady || editedHits.length === 0) return;

    const nearestIndex = editedHits.findIndex(h => Math.abs(h.time - currentTime) < 0.15);
    if (nearestIndex !== -1 && nearestIndex !== selectedHitIndex) {
      setSelectedHitIndex(nearestIndex);
    }
  }, [currentTime, isReady, editedHits, selectedHitIndex]);

  const togglePlay = async () => {
    if (!isPlaying) {
      const ctx = initAudioContext();
      if (ctx && ctx.state === 'suspended') await ctx.resume();
      
      const playables = stemNames.map((n) => audioElementsRef.current[n]).filter(Boolean);
      try {
        await Promise.all(playables.map((a) => a.play()));
        setIsPlaying(true);
      } catch (e) {
        console.error("Erro ao reproduzir no Inspetor:", e);
      }
    } else {
      stemNames.forEach((n) => audioElementsRef.current[n]?.pause());
      setIsPlaying(false);
    }
  };

  const handleSeek = (time) => {
    stemNames.forEach((name) => {
      const el = audioElementsRef.current[name];
      if (el) el.currentTime = time;
    });
    setCurrentTime(time);
    if (wavesurfer) wavesurfer.setTime(time);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveDrumCorrectionsAction(session.session_id, editedHits);
    } finally {
      setSaving(false);
    }
  };

  // Atalhos: Espaço (play/pause), setas (retroceder/avançar — Shift pra passo
  // maior) e Ctrl+S (salvar correções), todos ignorados enquanto o foco está
  // num campo de texto.
  useKeyboardShortcuts([
    { code: "Space", handler: () => togglePlay() },
    { code: "ArrowRight", handler: (e) => handleSeek(currentTimeRef.current + (e.shiftKey ? 0.5 : 0.05)) },
    { code: "ArrowLeft", handler: (e) => handleSeek(currentTimeRef.current - (e.shiftKey ? 0.5 : 0.05)) },
    { key: "s", ctrl: true, handler: () => handleSave() },
  ]);

  // Corrigir artista/música de uma sessão já processada (sem passar pelo
  // wizard de novo) e rebuscar o MIDI de mercado sob demanda — não precisa
  // reprocessar áudio, a análise de bateria salva já é reaproveitada.
  const handleToggleIdentityEdit = async () => {
    if (identityEditOpen) {
      setIdentityEditOpen(false);
      return;
    }
    setIdentityEditOpen(true);
    try {
      const saved = await getMusicIdentity(session.session_id);
      if (saved) {
        identity.initFrom({ artist: saved.artist_text, title: saved.title_text, url: saved.source_url });
      } else {
        identity.initFrom(session.selected_track);
      }
    } catch {
      identity.initFrom(session.selected_track);
    }
  };

  const handleSaveIdentity = async () => {
    const ok = await identity.save(session.session_id);
    if (!ok) return;
    await workspace.rematchMarketMidiAction(session.session_id);
    setIdentityEditOpen(false);
  };

  const identityEdit = {
    open: identityEditOpen,
    onToggle: handleToggleIdentityEdit,
    artistText: identity.artistText,
    titleText: identity.titleText,
    setTitleText: identity.setTitleText,
    onArtistTextChange: identity.handleArtistTextChange,
    selectedArtistId: identity.selectedArtistId,
    suggestions: identity.suggestions,
    resolving: identity.resolving,
    pickSuggestion: identity.pickSuggestion,
    saving: identity.confirming,
    error: identity.error,
    onSave: handleSaveIdentity,
  };

  return (
    <>
      <div style={{ display: "none" }}>
        {stemNames.map((name) => (
          <audio
            key={name}
            ref={(el) => (audioElementsRef.current[name] = el)}
            src={getStemAudioUrl(session.job_id, name)}
            crossOrigin="anonymous"
          />
        ))}
      </div>

      <DrumInspectorPage
        session={session}
        analysis={drumAnalysis}
        marketMidiStatus={marketMidiStatus}
        editedHits={editedHits}
        containerRef={containerRef}
        isReady={isReady}
        isPlaying={isPlaying}
        currentTime={currentTime}
        playbackSpeed={playbackSpeed}
        setPlaybackSpeed={setPlaybackSpeed}
        selectedHitIndex={selectedHitIndex}
        setSelectedHitIndex={setSelectedHitIndex}
        onTogglePlay={togglePlay}
        onSeek={handleSeek}
        onSave={handleSave}
        saving={saving}
        onBack={onBack}
        zoomLevel={zoomLevel}
        onZoom={setZoomLevel}
        scrollRef={scrollRef}
        onTriggerAnalysis={() => workspace.triggerDrumAnalysisAction(session.session_id)}
        identityEdit={identityEdit}
      />
    </>
  );
}

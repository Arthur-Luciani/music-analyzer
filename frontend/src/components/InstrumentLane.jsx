import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";

export default function InstrumentLane({
  stemName,
  label,
  audioUrl,
  volume,
  pan,
  isMuted,
  isSolo,
  onVolumeChange,
  onMuteToggle,
  onSoloToggle,
  onInspectorClick,
  isPlaying,
  onSeek,
  onRegister,
  accentColor = "var(--accent)"
}) {
  const waveContainerRef = useRef(null);
  const wavesurferRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Inicializa o WaveSurfer
  useEffect(() => {
    if (!waveContainerRef.current) return;

    const ws = WaveSurfer.create({
      container: waveContainerRef.current,
      waveColor: "#4c5560",
      progressColor: accentColor,
      cursorColor: "transparent", // Usamos o playhead global
      barWidth: 2,
      barGap: 3,
      barRadius: 2,
      height: 120,
      interact: false, // O scroll e seek são controlados pelo WorkspacePage
      normalize: true,
      hideScrollbar: true,
    });

    wavesurferRef.current = ws;
    let unregister;

    ws.on("ready", () => {
      setIsLoaded(true);
      if (onRegister) unregister = onRegister(ws);
    });

    return () => {
      if (unregister) unregister();
      ws.destroy();
    };
  }, [accentColor, onRegister]);

  // Carrega o áudio quando a URL mudar
  useEffect(() => {
    if (wavesurferRef.current && audioUrl) {
      wavesurferRef.current.load(audioUrl);
    }
  }, [audioUrl]);

  const handleVisualClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    if (onSeek) onSeek(percent);
  };

  return (
    <article className="instrument-lane animate-up">
      <div className="lane-header">
        <div className="lane-title-group">
          <strong style={{ color: isSolo ? "var(--warn)" : "inherit" }}>
            {label}
          </strong>
          {onInspectorClick && (
            <button className="pill-btn" onClick={onInspectorClick}>
              INSPETOR →
            </button>
          )}
        </div>

        <div className="lane-volume-control" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 4 }}>
            <span style={{ color: 'var(--text-muted)' }}>VOLUME</span>
            <span className="mono">{volume}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={volume}
            onChange={(e) => onVolumeChange(Number(e.target.value))}
            style={{ width: '100%', accentColor: accentColor }}
          />
        </div>

        <div className="lane-controls">
          <button 
            className={`pill-btn ${isSolo ? "active" : ""}`} 
            onClick={onSoloToggle}
          >
            SOLO
          </button>
          <button 
            className={`pill-btn ${isMuted ? "active" : ""}`} 
            onClick={onMuteToggle}
          >
            MUTE
          </button>
        </div>
      </div>

      <div 
        className="lane-visual" 
        onClick={handleVisualClick}
        style={{ cursor: 'pointer' }}
      >
        <div ref={waveContainerRef} style={{ width: '100%', height: '100%' }} />
        {/* Playhead individual da trilha para evitar vazamentos entre trilhas */}
        <div className="playhead" />
      </div>
    </article>
  );
}

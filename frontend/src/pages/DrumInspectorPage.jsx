import React, { useMemo, useEffect, useRef } from 'react';
import GrooveAnalyzer from '../components/GrooveAnalyzer';
import SheetMusicView from '../components/SheetMusicView';
import MusicIdentityEditPanel from '../components/MusicIdentityEditPanel';
import './DrumInspectorPage.css';

function getMarketMidiBadgeInfo(marketMidiStatus) {
  if (marketMidiStatus?.status === 'applied') {
    const score = Math.round(marketMidiStatus.match_score || 0);
    return {
      label: 'MIDI: MERCADO',
      className: 'market',
      title: `${marketMidiStatus.matched_artist} — ${marketMidiStatus.matched_title} (${score}% de confiança)`,
    };
  }
  return {
    label: 'MIDI: GERADO (IA)',
    className: 'generated',
    title: 'Nenhum MIDI de mercado encontrado com confiança suficiente — usando a transcrição gerada pelo modelo.',
  };
}

const LANES = [
  { id: 'cymbal', label: 'Pratos', color: '#78baaf' },
  { id: 'hihat', label: 'Chimbal', color: '#c18a3a' },
  { id: 'tom', label: 'Surdo / Tons', color: '#6b78ba' },
  { id: 'snare', label: 'Caixa', color: '#5ba17a' },
  { id: 'kick', label: 'Bumbo', color: '#ba6b78' },
];

export default function DrumInspectorPage({
  session,
  analysis,
  marketMidiStatus,
  editedHits,
  containerRef,
  isReady,
  isPlaying,
  currentTime,
  playbackSpeed,
  setPlaybackSpeed,
  selectedHitIndex,
  setSelectedHitIndex,
  onTogglePlay,
  onSeek,
  onSave,
  saving,
  onBack,
  zoomLevel,
  onZoom,
  scrollRef,
  onTriggerAnalysis,
  identityEdit,
}) {
  const [viewMode, setViewMode] = React.useState('technical'); // technical | study
  const laneStackRef = useRef(null);
  const waveScrollRef = useRef(null);
  const phTopRef = useRef(null);
  const phGridRef = useRef(null);

  const hitsByLane = useMemo(() => {
    const grouped = { kick: [], snare: [], hihat: [], tom: [], cymbal: [], other: [] };
    editedHits.forEach((hit, index) => {
      const laneId = grouped[hit.type] ? hit.type : 'other';
      grouped[laneId].push({ ...hit, originalIndex: index });
    });
    return grouped;
  }, [editedHits]);

  const duration = analysis?.duration_seconds || 1;
  const zoomPx = zoomLevel * 10; // Fator de escala

  const latestTimeRef = useRef(currentTime);
  const lastUpdateRef = useRef(performance.now());

  // Sincroniza o ref sempre que a prop mudar
  useEffect(() => {
    latestTimeRef.current = currentTime;
    lastUpdateRef.current = performance.now();
  }, [currentTime]);

  // Loop de Sincronia de Alta Performance (Scrolling Timeline)
  useEffect(() => {
    let rafId;

    // Reinicia a base da interpolação sempre que este loop (re)começa — sem
    // isso, se o player ficar parado por alguns segundos (aberto no modo
    // pause, ou logo após abrir o inspector) e o usuário der play, o próximo
    // frame calcula um `dt` do tamanho de todo o tempo parado, faz o
    // playhead saltar pra frente por 1-2 frames, e no frame seguinte
    // "corrige" de volta pra posição real — visualmente parece a linha
    // "ir pra trás e sumir".
    latestTimeRef.current = currentTime;
    lastUpdateRef.current = performance.now();

    const sync = () => {
      const now = performance.now();
      const dt = (now - lastUpdateRef.current) / 1000;

      let interpolatedTime = latestTimeRef.current;
      if (isPlaying) {
        interpolatedTime += dt * (playbackSpeed || 1);
      }

      const container = scrollRef.current;
      if (container) {
        const viewWidth = container.offsetWidth;
        const labelWidth = 180; // Largura fixa das labels à esquerda
        
        // A "mira" deve ser 25% da área ÚTIL (área da waveform)
        const activeAreaWidth = viewWidth - labelWidth;
        const threshold = labelWidth + (activeAreaWidth * 0.25);
        
        const x = interpolatedTime * zoomPx + labelWidth; 

        let finalPlayheadX = x;
        let finalScrollX = 0;

        if (x > threshold) {
          // Travamos o playhead na mira e scrollamos o conteúdo
          finalPlayheadX = threshold;
          finalScrollX = x - threshold;
        }

        // 1. Move playheads (camada fixa)
        if (phTopRef.current) phTopRef.current.style.left = `${finalPlayheadX}px`;
        if (phGridRef.current) phGridRef.current.style.left = `${finalPlayheadX}px`;
        
        // 2. Sincroniza Scroll de ambos os containers
        container.scrollLeft = finalScrollX;
        if (waveScrollRef.current) waveScrollRef.current.scrollLeft = finalScrollX;
      }

      rafId = requestAnimationFrame(sync);
    };

    rafId = requestAnimationFrame(sync);
    return () => cancelAnimationFrame(rafId);
    // currentTime é lido apenas para inicializar a base da interpolação no
    // instante em que o loop (re)começa — não deve disparar um restart a
    // cada frame (isso tornaria a interpolação inútil).
  }, [isPlaying, zoomPx, scrollRef, playbackSpeed]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sincroniza o scroll entre waveform e grid
  const handleScroll = (e) => {
    if (waveScrollRef.current && e.target === scrollRef.current) {
      waveScrollRef.current.scrollLeft = e.target.scrollLeft;
    }
  };

  // Clique na waveform de referência busca (seek) a mesma posição —
  // mesma matemática (zoomPx, labelWidth 180px) usada pelo loop de sincronia acima.
  const handleWaveformClick = (e) => {
    const container = waveScrollRef.current;
    if (!container) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left + container.scrollLeft;
    const time = (clickX - 180) / zoomPx;
    onSeek(Math.max(0, Math.min(duration, time)));
  };

  const renderMarkers = (laneId, color) => {
    return (hitsByLane[laneId] || []).map((hit) => (
      <div
        key={`${laneId}-${hit.originalIndex}`}
        className={`hit-marker ${selectedHitIndex === hit.originalIndex ? 'selected' : ''}`}
        style={{ 
          left: `${hit.time * zoomPx}px`,
          backgroundColor: color,
          boxShadow: `0 0 12px ${color}66`
        }}
        onClick={(e) => {
          e.stopPropagation();
          setSelectedHitIndex(hit.originalIndex);
          onSeek(hit.time);
        }}
      />
    ));
  };

  const midiBadge = getMarketMidiBadgeInfo(marketMidiStatus);

  const formatClock = (seconds) => {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}:${String(ms).padStart(2, '0')}`;
  };

  return (
    <div className="drum-inspector-layout">
      {/* 1. Top Bar */}
      <header className="inspector-header">
        <div className="header-left">
          <button className="btn-ui" onClick={onBack}>← VOLTAR AO MIXER</button>
          <div className="header-divider"></div>
          <h1>Drum Inspector: <span className="session-name">{session?.name}</span></h1>
          <div className="midi-badge-wrap">
            <span className={`midi-source-badge ${midiBadge.className}`} title={midiBadge.title}>
              {midiBadge.label}
            </span>
            <button type="button" className="midi-edit-trigger" onClick={identityEdit.onToggle}>
              Editar
            </button>
            {identityEdit.open && (
              <MusicIdentityEditPanel
                artistText={identityEdit.artistText}
                titleText={identityEdit.titleText}
                setTitleText={identityEdit.setTitleText}
                onArtistTextChange={identityEdit.onArtistTextChange}
                selectedArtistId={identityEdit.selectedArtistId}
                suggestions={identityEdit.suggestions}
                resolving={identityEdit.resolving}
                pickSuggestion={identityEdit.pickSuggestion}
                saving={identityEdit.saving}
                error={identityEdit.error}
                onSave={identityEdit.onSave}
                onCancel={identityEdit.onToggle}
              />
            )}
          </div>
        </div>
        
        <div className="header-right">
          <div className="view-controls">
            <div className="zoom-control">
              <button className="zoom-btn" onClick={() => onZoom(Math.max(5, zoomLevel - 5))} title="Diminuir zoom">−</button>
              <span className="zoom-label">ZOOM</span>
              <button className="zoom-btn" onClick={() => onZoom(Math.min(80, zoomLevel + 5))} title="Aumentar zoom">+</button>
            </div>
            <div className="speed-control">
              {[0.5, 1, 1.5, 2].map((speed) => (
                <button
                  key={speed}
                  className={`pill-btn speed-btn ${playbackSpeed === speed ? 'active' : ''}`}
                  onClick={() => setPlaybackSpeed(speed)}
                >
                  {speed}x
                </button>
              ))}
            </div>
          </div>
          <div className="header-divider"></div>
          <div className="mode-toggle">
            <button 
              className={`pill-btn ${viewMode === 'technical' ? 'active' : ''}`}
              onClick={() => setViewMode('technical')}
            >
              INSPETOR TÉCNICO
            </button>
            <button
              className={`pill-btn ${viewMode === 'study' ? 'active' : ''}`}
              onClick={() => setViewMode('study')}
            >
              MODO DE ESTUDO
            </button>
            <button
              className={`pill-btn ${viewMode === 'score' ? 'active' : ''}`}
              onClick={() => setViewMode('score')}
            >
              PARTITURA
            </button>
          </div>
          <div className="header-divider"></div>
          <button 
            className="btn-ui save-btn" 
            onClick={onSave}
            disabled={saving}
          >
            {saving ? 'SALVANDO...' : 'SALVAR AJUSTES'}
          </button>
        </div>
      </header>

      {/* 2. Control Dashboard (Padrao do Estúdio) — logo após o header, sempre visível sem scroll */}
      <section className="control-dashboard">
        <div className="dashboard-group">
          <button className="btn-transport" onClick={() => onSeek(0)}>|&lt;</button>
          <button className="btn-transport" onClick={() => onSeek(currentTime - 5)}>-5s</button>
          <button
            className="btn-transport play"
            onClick={onTogglePlay}
          >
            {isPlaying ? "PAUSAR" : "REPRODUZIR"}
          </button>
          <button className="btn-transport" onClick={() => onSeek(currentTime + 5)}>+5s</button>
        </div>

        <div className="time-display-pro">{formatClock(currentTime)}</div>

        <div className="dashboard-divider"></div>

        <div className="dashboard-group">
          <div className="footer-stats">
            <div className="stat">BPM: <strong>{analysis?.bpm}</strong></div>
            <div className="stat">GOLPES: <strong>{editedHits.length}</strong></div>
            <div className="stat">PEÇA: <strong style={{ color: 'var(--accent)' }}>{selectedHitIndex !== null ? editedHits[selectedHitIndex].type.toUpperCase() : '--'}</strong></div>
          </div>
        </div>
      </section>

      {/* Única região que rola verticalmente — controles/header/footer ficam sempre visíveis */}
      <div className="inspector-content-area">
        {viewMode === 'technical' ? (
          <>
            {/* Onda de Referência (Waveform Master) */}
            <section
              className="master-wave-wrap scroll-container"
              ref={waveScrollRef}
              style={{ overflow: 'hidden' }}
              onClick={handleWaveformClick}
            >
              <div className="playhead" id="ph-top" ref={phTopRef} style={{ height: '100%' }}></div>
              <div className="timeline-content" style={{ width: `${duration * zoomPx + 200}px` }}>
                <div className="waveform-container" ref={containerRef}></div>
              </div>
            </section>

            {/* Grid de Edição Técnica */}
            <main className="drum-grid">
              <div
                className="grid-scroll-area"
                ref={scrollRef}
                onScroll={handleScroll}
                style={{ position: 'relative' }}
              >
                <div
                  className="playhead"
                  id="ph-grid"
                  ref={phGridRef}
                  style={{ height: '100%' }}
                ></div>

                <div className="timeline-content" style={{ width: `${duration * zoomPx + 200}px` }}>
                  <div className="ruler">
                    {Array.from({ length: Math.ceil(duration / 5) }).map((_, i) => (
                      <div key={i} className="ruler-mark" style={{ left: `${i * 5 * zoomPx + 180}px` }}>
                        00:{String(i * 5).padStart(2, '0')}:00
                      </div>
                    ))}
                  </div>

                  <div id="lane-stack" ref={laneStackRef}>
                    {LANES.map(lane => (
                      <div key={lane.id} className="lane">
                        <div className="label" style={{ borderRight: `4px solid ${lane.color}` }}>
                          {lane.label}
                        </div>
                        <div className="lane-hit-area">
                          {renderMarkers(lane.id, lane.color)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </main>
          </>
        ) : viewMode === 'study' ? (
          <main className="study-mode-content" style={{ padding: '24px' }}>
            <GrooveAnalyzer
              patterns={analysis?.patterns || []}
              bpm={analysis?.bpm || 120}
              onTriggerAnalysis={onTriggerAnalysis}
              sessionId={session?.session_id}
            />
          </main>
        ) : (
          <SheetMusicView
            sessionId={session?.session_id}
            bpm={analysis?.bpm || 120}
            currentTime={currentTime}
            onSeek={onSeek}
          />
        )}
      </div>

      {/* Painel de Atalhos */}
      <footer className="inspector-footer-pro">
        <div className="footer-shortcuts">
          <span className="kbd">ESPAÇO</span> Play/Pause 
          <span className="kbd">K</span> Bumbo 
          <span className="kbd">S</span> Caixa 
          <span className="kbd">H</span> Chimbal 
          <span className="kbd">A</span> Adicionar
          <span className="kbd">DEL</span> Remover
          <span className="kbd">←/→</span> Navegação
        </div>
      </footer>
    </div>
  );
}

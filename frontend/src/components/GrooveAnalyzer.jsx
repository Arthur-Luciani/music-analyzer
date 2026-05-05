import React, { useState, useEffect, useRef } from 'react';
import './GrooveAnalyzer.css';
import { getDrumSamples } from '../api';

const PIECES = [
  { id: 'hihat', label: 'CHIMBAL', color: 'var(--accent)', key: 'h' },
  { id: 'snare', label: 'CAIXA', color: 'var(--good)', key: 's' },
  { id: 'tom', label: 'TONS / SURDO', color: '#6b78ba', key: 't' },
  { id: 'kick', label: 'BUMBO', color: 'var(--bad)', key: 'k' },
];

export default function GrooveAnalyzer({ patterns, bpm, onTriggerAnalysis, sessionId }) {
  const [selectedPatternIndex, setSelectedPatternIndex] = useState(0);
  const [learningLevel, setLearningLevel] = useState(4); // 1-4
  const [isPlaying, setIsPlaying] = useState(false);
  const [samples, setSamples] = useState(null); // { kick: AudioBuffer, ... }
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [kitType, setKitType] = useState('studio'); // 'original' | 'studio'

  const audioCtxRef = useRef(null);
  const nextNoteTimeRef = useRef(0);
  const current16thNoteRef = useRef(0);
  const timerIDRef = useRef(null);

  const STUDIO_SAMPLES = {
    kick: '/assets/drums/kick_pro.wav',
    snare: '/assets/drums/snare_pro.wav',
    hihat: '/assets/drums/hihat_pro.wav',
    tom: '/assets/drums/tom_pro.wav',
  };

  // Carregar samples ao montar ou trocar de sessão/kit
  useEffect(() => {
    const loadSamples = async () => {
      setIsLoadingSamples(true);
      try {
        const ctx = audioCtxRef.current || new (window.AudioContext || window.webkitAudioContext)();
        audioCtxRef.current = ctx;

        let sampleUrls = {};
        if (kitType === 'original' && sessionId) {
          sampleUrls = await getDrumSamples(sessionId);
        } else {
          sampleUrls = STUDIO_SAMPLES;
        }

        const buffers = {};
        await Promise.all(
          Object.entries(sampleUrls).map(async ([type, url]) => {
            const response = await fetch(url);
            const arrayBuffer = await response.arrayBuffer();
            buffers[type] = await ctx.decodeAudioData(arrayBuffer);
          })
        );
        setSamples(buffers);
      } catch (err) {
        console.error("Erro ao carregar samples:", err);
      } finally {
        setIsLoadingSamples(false);
      }
    };

    loadSamples();
    
    return () => {
      if (timerIDRef.current) clearTimeout(timerIDRef.current);
    };
  }, [sessionId, kitType]);

  const currentPattern = patterns[selectedPatternIndex];
  const gridLength = currentPattern?.kick?.length || 16;

  // Sequencer Logic
  const scheduleNote = (noteNumber, time) => {
    if (!samples || !currentPattern) return;

    PIECES.forEach(piece => {
      const bits = getDisplayBits(piece.id, currentPattern[piece.id] || '0'.repeat(gridLength));
      if (bits[noteNumber] === '1' && samples[piece.id]) {
        const source = audioCtxRef.current.createBufferSource();
        source.buffer = samples[piece.id];
        source.connect(audioCtxRef.current.destination);
        source.start(time);
      }
    });
  };

  const nextNote = () => {
    const secondsPerBeat = 60.0 / bpm;
    // Se grid=12 (tercinado), cada nota é 1/3 de beat. Se grid=16, é 1/4.
    const divisionsPerBeat = gridLength / 4;
    nextNoteTimeRef.current += (1.0 / divisionsPerBeat) * secondsPerBeat;
    current16thNoteRef.current = (current16thNoteRef.current + 1) % gridLength;
  };

  const scheduler = () => {
    while (nextNoteTimeRef.current < audioCtxRef.current.currentTime + 0.1) {
      scheduleNote(current16thNoteRef.current, nextNoteTimeRef.current);
      nextNote();
    }
    timerIDRef.current = setTimeout(scheduler, 25);
  };

  const togglePlayback = async () => {
    if (isPlaying) {
      if (timerIDRef.current) clearTimeout(timerIDRef.current);
      setIsPlaying(false);
    } else {
      if (audioCtxRef.current.state === 'suspended') {
        await audioCtxRef.current.resume();
      }
      current16thNoteRef.current = 0;
      nextNoteTimeRef.current = audioCtxRef.current.currentTime + 0.05;
      setIsPlaying(true);
      scheduler();
    }
  };

  if (!patterns || patterns.length === 0) {
    return (
      <div className="groove-analyzer-empty card">
        <div className="empty-icon">🥁</div>
        <p>Nenhum padrão de groove identificado nesta sessão.</p>
        <p style={{ fontSize: '11px', marginBottom: '20px' }}>
          Sessões antigas precisam ser re-processadas para extrair assinaturas rítmicas.
        </p>
        <button 
          className="btn-accent" 
          onClick={onTriggerAnalysis}
        >
          IDENTIFICAR GROOVES AGORA
        </button>
      </div>
    );
  }

  // Lógica de simplificação pedagógica (Scaffolding)
  const getDisplayBits = (pieceId, originalBits) => {
    if (learningLevel === 4) return originalBits;
    
    const bits = originalBits.split('');
    
    if (learningLevel === 1) {
      // Nível 1: Apenas Bumbo e Caixa nos tempos 1, 2, 3, 4
      if (pieceId === 'hihat') return '0'.repeat(gridLength);
      const divPerBeat = gridLength / 4;
      return bits.map((b, i) => (i % divPerBeat === 0 ? b : '0')).join('');
    }
    
    if (learningLevel === 2) {
      // Nível 2: Bumbo e Caixa completos, sem pratos
      if (pieceId === 'hihat') return '0'.repeat(gridLength);
      return originalBits;
    }
    
    if (learningLevel === 3) {
      // Nível 3: Bumbo/Caixa completos + Chimbal em colcheias (8th notes / ternary division)
      if (pieceId === 'hihat') {
        const skip = gridLength === 12 ? 3 : 2; // se 12 slots, mostrar no início do beat
        return bits.map((b, i) => (i % skip === 0 ? b : '0')).join('');
      }
      return originalBits;
    }
    
    return originalBits;
  };

  return (
    <div className="groove-analyzer-container animate-up">
      <div className="groove-main-card card">
        <div className="groove-card-header">
          <div className="groove-title-group">
            <span className="kicker">Modo de Estudo</span>
            <h2>Assinatura de Groove</h2>
            <p>Padrão recorrente detectado {currentPattern.frequency} vezes na track.</p>
          </div>
          <div className="groove-header-actions">
            <div className="kit-selector">
              <button 
                className={`kit-btn ${kitType === 'original' ? 'active' : ''}`}
                onClick={() => setKitType('original')}
                title="Sons extraídos da música"
              >
                Kit Original
              </button>
              <button 
                className={`kit-btn ${kitType === 'studio' ? 'active' : ''}`}
                onClick={() => setKitType('studio')}
                title="Sons de estúdio limpos"
              >
                Kit Estúdio
              </button>
            </div>
            <button 
              className={`groove-play-btn ${isPlaying ? 'playing' : ''}`}
              onClick={togglePlayback}
              disabled={isLoadingSamples || !samples}
            >
              {isLoadingSamples ? 'CARREGANDO...' : isPlaying ? 'PARAR LOOP' : 'OUVIR GROOVE'}
            </button>
            <div className="groove-stats">
              <div className="mini-stat">
                <span className="mini-stat-label">BPM</span>
                <span className="mini-stat-value">{bpm}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="groove-matrix">
          {PIECES.map(piece => {
            const bits = getDisplayBits(piece.id, currentPattern[piece.id] || '0'.repeat(gridLength));
            return (
              <div key={piece.id} className="matrix-row">
                <div className="matrix-label">{piece.label}</div>
                <div className="matrix-cells">
                    {bits.split('').map((bit, i) => {
                      const groupSize = gridLength / 4;
                      return (
                        <div 
                          key={i} 
                          className={`matrix-cell ${bit === '1' ? `active-${piece.key}` : ''} ${i === current16thNoteRef.current && isPlaying ? 'playing' : ''}`}
                          style={{ 
                            '--cell-color': piece.color,
                            marginRight: (i + 1) % groupSize === 0 && i < gridLength - 1 ? '10px' : '2px'
                          }}
                        />
                      );
                    })}
                </div>
              </div>
            );
          })}
        </div>

        <div className="learning-path-section">
          <h3>Trilha de Aprendizado Progressiva</h3>
          <div className="learning-path-steps">
            {[
              { lv: 1, label: 'Fundação', desc: 'Base 1 e 3' },
              { lv: 2, label: 'Esqueleto', desc: 'Sem Pratos' },
              { lv: 3, label: 'Pulso', desc: 'Com Chimbal' },
              { lv: 4, label: 'Groove Real', desc: 'Original' },
            ].map(step => (
              <button 
                key={step.lv}
                className={`path-step-btn ${learningLevel === step.lv ? 'active' : ''}`}
                onClick={() => setLearningLevel(step.lv)}
              >
                <span className="step-number">{step.lv}</span>
                <div className="step-info">
                  <span className="step-label">{step.label}</span>
                  <span className="step-desc">{step.desc}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="groove-sidebar">
        <div className="card">
          <span className="kicker" style={{ color: 'var(--accent)' }}>Variações</span>
          <div className="pattern-selector">
            {patterns.map((p, i) => (
              <button 
                key={i}
                className={`pattern-btn ${selectedPatternIndex === i ? 'active' : ''}`}
                onClick={() => setSelectedPatternIndex(i)}
              >
                <div className="pattern-btn-head">
                  <strong>{p.name}</strong>
                  <span>{p.frequency}x</span>
                </div>
                <div className="pattern-mini-preview">
                  {p.kick.split('').map((b, idx) => (
                    <div key={idx} className={`mini-dot ${b === '1' ? 'active' : ''}`} />
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

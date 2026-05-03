import React, { useEffect, useRef, useState } from 'react';

const PIXELS_PER_SECOND = 60; // Sync with Workspace

const StemWaveform = ({ url, currentTime, duration, color = 'rgba(193, 138, 58, 0.5)' }) => {
  const canvasRef = useRef(null);
  const [audioBuffer, setAudioBuffer] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!url) return;
    
    const fetchAudio = async () => {
      setLoading(true);
      try {
        const response = await fetch(url);
        const arrayBuffer = await response.arrayBuffer();
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const decodedData = await audioCtx.decodeAudioData(arrayBuffer);
        setAudioBuffer(decodedData);
      } catch (err) {
        console.error('Error loading waveform:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAudio();
  }, [url]);

  useEffect(() => {
    if (!audioBuffer || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const data = audioBuffer.getChannelData(0);
    const step = Math.ceil(data.length / canvas.width);
    const amp = canvas.height / 2;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, color);
    gradient.addColorStop(0.5, color.replace('0.5', '0.8'));
    gradient.addColorStop(1, color);
    
    ctx.fillStyle = gradient;

    for (let i = 0; i < canvas.width; i++) {
      let min = 1.0;
      let max = -1.0;
      for (let j = 0; j < step; j++) {
        const datum = data[i * step + j];
        if (datum < min) min = datum;
        if (datum > max) max = datum;
      }
      const y = (1 + min) * amp;
      const h = Math.max(1, (max - min) * amp);
      ctx.fillRect(i, y, 1, h);
    }
  }, [audioBuffer, color]);

  const totalWidth = duration * PIXELS_PER_SECOND;
  const playheadPos = currentTime * PIXELS_PER_SECOND;
  const scrollOffset = Math.max(0, playheadPos - 100); // 100 is PLAYHEAD_OFFSET

  return (
    <div className="stem-waveform-container" style={{ width: '100%', height: '100%', overflow: 'hidden', position: 'relative' }}>
      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: '#444' }}>
          CARREGANDO ONDA...
        </div>
      )}
      <div 
        className="waveform-wrapper" 
        style={{ 
          width: `${totalWidth}px`, 
          height: '100%', 
          position: 'absolute',
          transform: `translateX(-${scrollOffset}px)`,
          transition: 'transform 0.1s linear'
        }}
      >
        <canvas
          ref={canvasRef}
          width={totalWidth}
          height={100}
          style={{ width: `${totalWidth}px`, height: '100%', display: 'block' }}
        />
      </div>
    </div>
  );
};

export default StemWaveform;

import { useEffect, useRef, useState, useCallback } from "react";

// Converte ganho percentual para escala linear (0.0 a 1.0 ou + pra master)
function percentToGain(percent) {
  if (!Number.isFinite(percent)) return 0.6;
  return Math.max(0, Math.min(percent / 100, 1));
}

export function useWebAudioMixer({
  stemNames,
  audioElementsRef,
  mixLevels,
  panLevels,
  mutedStems,
  soloStem,
  isPlaying,
}) {
  const [meters, setMeters] = useState({ masterL: 0, masterR: 0, stems: {} });
  const [isInitialized, setIsInitialized] = useState(false);

  const ctxRef = useRef(null);
  const nodesRef = useRef({}); // por stemName: { source, gain, pan, analyser }
  const masterNodesRef = useRef(null); // { gain, splitter, analyserL, analyserR }
  const rAFRef = useRef(null);

  // Inicializa contexto de audio ao tentar tocar pela primeira vez
  const initAudioContext = useCallback(() => {
    if (ctxRef.current) return;

    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    ctxRef.current = ctx;

    // Master bus
    const masterGain = ctx.createGain();
    const masterSplitter = ctx.createChannelSplitter(2);
    const analyzerL = ctx.createAnalyser();
    const analyzerR = ctx.createAnalyser();
    
    analyzerL.fftSize = 512;
    analyzerL.smoothingTimeConstant = 0.8;
    analyzerR.fftSize = 512;
    analyzerR.smoothingTimeConstant = 0.8;

    masterGain.connect(masterSplitter);
    masterSplitter.connect(analyzerL, 0);
    masterSplitter.connect(analyzerR, 1);
    masterGain.connect(ctx.destination);

    masterNodesRef.current = {
      gain: masterGain,
      analyserL: analyzerL,
      analyserR: analyzerR,
    };

    setIsInitialized(true);
  }, []);

  // Connect stems
  useEffect(() => {
    if (!ctxRef.current) return;

    // Garante que o contexto está ativo (essencial para Chrome/Edge)
    if (isPlaying && ctxRef.current.state === "suspended") {
      ctxRef.current.resume();
    }

    stemNames.forEach((stemName) => {
      const audioNode = audioElementsRef.current[stemName];
      if (!audioNode) return;

      // Se o nó já existe mas o source não está conectado ao contexto atual, limpamos para reconectar
      if (!nodesRef.current[stemName]) {
        try {
          const source = ctxRef.current.createMediaElementSource(audioNode);
          const pan = ctxRef.current.createStereoPanner();
          const gain = ctxRef.current.createGain();
          const analyser = ctxRef.current.createAnalyser();

          analyser.fftSize = 512;
          analyser.smoothingTimeConstant = 0.8;

          source.connect(pan);
          pan.connect(gain);
          gain.connect(analyser);
          analyser.connect(masterNodesRef.current.gain);

          nodesRef.current[stemName] = { source, pan, gain, analyser };
          console.log(`Conectado stem: ${stemName}`);
        } catch (e) {
          // Erro comum se já estiver conectado, mas o log ajuda no debug
          console.warn(`Aviso ao conectar stem ${stemName}:`, e.message);
        }
      }
    });
  }, [stemNames, audioElementsRef, isPlaying, isInitialized]);

  // Aplicar Mute, Solo, Volume, Pan
  useEffect(() => {
    if (!ctxRef.current) return;

    const masterLevel = mixLevels?.master ?? 78;
    if (masterNodesRef.current) {
      masterNodesRef.current.gain.gain.setTargetAtTime(percentToGain(masterLevel), ctxRef.current.currentTime, 0.05);
    }

    stemNames.forEach((stemName) => {
      const bag = nodesRef.current[stemName];
      if (!bag) return;

      // Logica de fader
      const stemLevel = mixLevels?.[stemName] ?? 60;
      let targetGain = percentToGain(stemLevel);

      // Logica mute/solo
      const isMutedBySolo = Boolean(soloStem) && soloStem !== stemName;
      const isMutedByToggle = Boolean(mutedStems[stemName]);
      
      if (isMutedBySolo || isMutedByToggle) {
        targetGain = 0;
      }

      bag.gain.gain.setTargetAtTime(targetGain, ctxRef.current.currentTime, 0.05);

      // Logica pan (-100 to 100 -> -1.0 to 1.0)
      const panVal = (panLevels[stemName] ?? 0) / 100;
      bag.pan.pan.setTargetAtTime(panVal, ctxRef.current.currentTime, 0.05);
    });
  }, [stemNames, mixLevels, panLevels, mutedStems, soloStem, isInitialized]);

  // Request Animation Frame loop para levels
  useEffect(() => {
    if (!isPlaying) {
      if (rAFRef.current) cancelAnimationFrame(rAFRef.current);
      // Keep displaying zeros or wait for drop
      setMeters({ masterL: 0, masterR: 0, stems: {} });
      return;
    }

    const calcRMS = (array) => {
      let sum = 0;
      for (let i = 0; i < array.length; i++) {
        sum += ((array[i] - 128) / 128) * ((array[i] - 128) / 128);
      }
      return Math.sqrt(sum / array.length);
    };

    // converter 0.0 - 1.0 RMS para percentual ajustado +- visivel
    const rmsToPercent = (rms) => {
      if (rms === 0) return 0;
      const db = 20 * Math.log10(rms);
      // mapeia de -60 a 0 dB pra 0 a 100%
      const minDb = -48;
      let percent = ((db - minDb) / (0 - minDb)) * 100;
      return Math.max(0, Math.min(100, isNaN(percent) ? 0 : percent));
    };

    function updateMeters() {
      if (!ctxRef.current || !masterNodesRef.current) return;

      const newMeters = { masterL: 0, masterR: 0, stems: {} };
      const arrayL = new Uint8Array(512);
      const arrayR = new Uint8Array(512);

      masterNodesRef.current.analyserL.getByteTimeDomainData(arrayL);
      masterNodesRef.current.analyserR.getByteTimeDomainData(arrayR);

      newMeters.masterL = rmsToPercent(calcRMS(arrayL));
      newMeters.masterR = rmsToPercent(calcRMS(arrayR));

      stemNames.forEach((stemName) => {
        const bag = nodesRef.current[stemName];
        if (bag) {
          const arr = new Uint8Array(512);
          bag.analyser.getByteTimeDomainData(arr);
          newMeters.stems[stemName] = rmsToPercent(calcRMS(arr));
        } else {
          newMeters.stems[stemName] = 0;
        }
      });

      setMeters(newMeters);
      rAFRef.current = requestAnimationFrame(updateMeters);
    }

    // Retoma o audio caso esteja suspenso
    if (ctxRef.current && ctxRef.current.state === "suspended") {
      ctxRef.current.resume();
    }

    rAFRef.current = requestAnimationFrame(updateMeters);

    return () => {
      if (rAFRef.current) cancelAnimationFrame(rAFRef.current);
    };
  }, [isPlaying, stemNames]);

  return {
    initAudioContext,
    meters,
    ctx: ctxRef.current,
    masterNodes: masterNodesRef.current
  };
}

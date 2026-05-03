import { useState, useRef } from "react";
import { getMixState, updateMixState, createExportJob, listExportJobs, getDrumAnalysis, triggerDrumAnalysis, saveDrumCorrections as apiSaveDrumCorrections } from "../api";

const DEFAULT_MIX_LEVELS = {
  vocals: 72,
  drums: 72,
  bass: 72,
  other: 72,
  master: 72,
};

export function useWorkspace() {
  const [mixLevels, setMixLevels] = useState(DEFAULT_MIX_LEVELS);
  const [soloStem, setSoloStem] = useState("");
  const [mutedStems, setMutedStems] = useState({});
  const [panLevels, setPanLevels] = useState({});
  const [mixStateLoading, setMixStateLoading] = useState(false);
  const [mixStateSaving, setMixStateSaving] = useState(false);
  const [mixStateError, setMixStateError] = useState("");
  const [exportJobs, setExportJobs] = useState([]);
  const [exportJobsLoading, setExportJobsLoading] = useState(false);
  const [exportJobsError, setExportJobsError] = useState("");
  const [exportActionLoading, setExportActionLoading] = useState("");
  const [exportActionMessage, setExportActionMessage] = useState("");
  
  const [drumAnalysis, setDrumAnalysis] = useState(null);
  const [drumAnalysisLoading, setDrumAnalysisLoading] = useState(false);
  const [drumAnalysisError, setDrumAnalysisError] = useState("");
  
  const loadedMixSessionRef = useRef("");
  const lastPersistedMixRef = useRef("");

  // Convert 0-100% UI slider value → dB gain expected by the backend (-60..24 dB)
  function pctToDb(pct) {
    const normalized = Math.max(0, Math.min(100, Number(pct) || 0)) / 100;
    return parseFloat((normalized * 84 - 60).toFixed(2));
  }

  // Convert dB gain from backend (-60..24 dB) → 0-100% UI slider value
  function dbToPct(db) {
    const val = (Number(db) + 60) / 84;
    return Math.round(Math.max(0, Math.min(1, val)) * 100);
  }

  const fetchMixState = async (sessionId) => {
    if (!sessionId || loadedMixSessionRef.current === sessionId) return;

    setMixStateLoading(true);
    setMixStateError("");

    try {
      const data = await getMixState(sessionId);
      
      if (data && (data.per_stem || data.master_gain !== undefined)) {
        const levels = { ...DEFAULT_MIX_LEVELS };
        const mutes = {};
        const pans = {};
        let solo = "";
        
        if (data.master_gain !== undefined) {
          levels.master = dbToPct(data.master_gain);
        }
        
        if (data.per_stem) {
          Object.entries(data.per_stem).forEach(([name, state]) => {
            if (state && state.gain !== undefined) {
              levels[name] = dbToPct(state.gain);
            }
            if (state && state.mute) {
              mutes[name] = true;
            }
            if (state && state.solo) {
              solo = name;
            }
            if (state && state.pan !== undefined) {
              pans[name] = Math.round(state.pan * 100);
            }
          });
        }
        
        setMixLevels(levels);
        setMutedStems(mutes);
        setSoloStem(solo);
        setPanLevels(pans);
      } else {
        setMixLevels(DEFAULT_MIX_LEVELS);
        setMutedStems({});
        setSoloStem("");
        setPanLevels({});
      }
      
      loadedMixSessionRef.current = sessionId;
    } catch (err) {
      setMixStateError(err.message || "Falha ao carregar mix-state");
    } finally {
      setMixStateLoading(false);
    }
  };

  const saveMixState = async (sessionId, levels, solo, mutes, pans) => {
    if (!sessionId) return;

    setMixStateSaving(true);
    setMixStateError("");

    try {
      const STEM_NAMES = ["vocals", "drums", "bass", "other"];
      const per_stem = Object.fromEntries(
        STEM_NAMES
          .filter((name) => levels[name] !== undefined)
          .map((name) => [
            name,
            { 
              gain: pctToDb(levels[name]), 
              pan: (pans[name] ?? 0) / 100, 
              mute: Boolean(mutes[name]), 
              solo: solo === name, 
              send_fx: 0.0 
            },
          ])
      );
      const payload = {
        per_stem,
        master_gain: pctToDb(levels.master),
      };
      await updateMixState(sessionId, payload);
      lastPersistedMixRef.current = JSON.stringify({ levels, solo, mutes, pans });
    } catch (err) {
      setMixStateError(err.message || "Falha ao salvar mix-state");
    } finally {
      setMixStateSaving(false);
    }
  };

  const resetMixState = async (sessionId) => {
    if (!sessionId) return;
    
    const levels = { ...DEFAULT_MIX_LEVELS };
    const solo = "";
    const mutes = {};
    const pans = {};
    
    setMixLevels(levels);
    setSoloStem(solo);
    setMutedStems(mutes);
    setPanLevels(pans);
    
    await saveMixState(sessionId, levels, solo, mutes, pans);
  };

  const applyPreset = async (sessionId, presetLevels) => {
    if (!sessionId) return;
    
    const startLevels = { ...mixLevels };
    const duration = 400; // ms
    const startTime = performance.now();

    const animate = (time) => {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Easing function (easeOutQuad)
      const ease = progress * (2 - progress);

      const currentLevels = {};
      Object.keys(presetLevels).forEach((key) => {
        const start = startLevels[key] ?? 72;
        const target = presetLevels[key];
        currentLevels[key] = Math.round(start + (target - start) * ease);
      });

      setMixLevels((prev) => ({ ...prev, ...currentLevels }));

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        saveMixState(sessionId, { ...mixLevels, ...presetLevels }, "", {}, panLevels);
      }
    };

    setSoloStem("");
    setMutedStems({});
    requestAnimationFrame(animate);
  };

  const [userPresets, setUserPresets] = useState(() => {
    try {
      const saved = localStorage.getItem("mx_user_presets");
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const saveUserPreset = (name, levels) => {
    const next = { ...userPresets, [name]: levels };
    setUserPresets(next);
    localStorage.setItem("mx_user_presets", JSON.stringify(next));
  };

  const deleteUserPreset = (name) => {
    const next = { ...userPresets };
    delete next[name];
    setUserPresets(next);
    localStorage.setItem("mx_user_presets", JSON.stringify(next));
  };

  const fetchExports = async (sessionId) => {
    if (!sessionId) return;
    setExportJobsLoading(true);
    try {
      const jobs = await listExportJobs(sessionId);
      setExportJobs(Array.isArray(jobs) ? jobs : []);
    } catch {
      setExportJobsError("Falha ao carregar exportações");
    } finally {
      setExportJobsLoading(false);
    }
  };

  const createExport = async (sessionId, preset, format) => {
    if (!sessionId) return;
    setExportActionLoading(`${preset}:${format}`);
    try {
      await createExportJob(sessionId, { preset, format });
      setExportActionMessage(`Exportação ${preset} iniciada`);
      await fetchExports(sessionId);
    } catch {
      setExportJobsError("Falha ao criar exportação");
    } finally {
      setExportActionLoading("");
    }
  };

  const fetchDrumAnalysis = async (sessionId) => {
    if (!sessionId) return;
    setDrumAnalysisLoading(true);
    setDrumAnalysisError("");
    try {
      const data = await getDrumAnalysis(sessionId);
      setDrumAnalysis(data);
    } catch (err) {
      // 404 is expected if not analyzed yet
      if (err.status !== 404) {
        setDrumAnalysisError(err.message || "Falha ao carregar análise de bateria");
      }
      setDrumAnalysis(null);
    } finally {
      setDrumAnalysisLoading(false);
    }
  };

  const triggerDrumAnalysisAction = async (sessionId) => {
    if (!sessionId) return;
    setDrumAnalysisLoading(true);
    setDrumAnalysisError("");
    try {
      await triggerDrumAnalysis(sessionId);
      
      // Poll for results
      let attempts = 0;
      const maxAttempts = 20;
      const poll = async () => {
        try {
          const data = await getDrumAnalysis(sessionId);
          setDrumAnalysis(data);
          setDrumAnalysisLoading(false);
        } catch (err) {
          if (attempts < maxAttempts) {
            attempts++;
            setTimeout(poll, 2000);
          } else {
            setDrumAnalysisError("Tempo esgotado ao analisar bateria");
            setDrumAnalysisLoading(false);
          }
        }
      };
      
      setTimeout(poll, 3000);
    } catch (err) {
      setDrumAnalysisError(err.message || "Falha ao iniciar análise de bateria");
      setDrumAnalysisLoading(false);
    }
  };

  const saveDrumCorrectionsAction = async (sessionId, hits) => {
    if (!sessionId) return;
    setDrumAnalysisLoading(true);
    try {
      const data = await apiSaveDrumCorrections(sessionId, hits);
      setDrumAnalysis(data);
    } catch (err) {
      setDrumAnalysisError(err.message || "Falha ao salvar correções");
    } finally {
      setDrumAnalysisLoading(false);
    }
  };

  return {
    mixLevels,
    setMixLevels,
    soloStem,
    setSoloStem,
    mutedStems,
    setMutedStems,
    panLevels,
    setPanLevels,
    mixStateLoading,
    mixStateSaving,
    mixStateError,
    exportJobs,
    exportJobsLoading,
    exportJobsError,
    exportActionLoading,
    exportActionMessage,
    userPresets,
    fetchMixState,
    saveMixState,
    resetMixState,
    applyPreset,
    saveUserPreset,
    deleteUserPreset,
    fetchExports,
    createExport,
    drumAnalysis,
    drumAnalysisLoading,
    drumAnalysisError,
    fetchDrumAnalysis,
    triggerDrumAnalysisAction,
    saveDrumCorrectionsAction,
  };
}

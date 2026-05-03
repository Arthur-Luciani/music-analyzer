import { useEffect, useMemo, useRef } from "react";
import { useSession } from "../context/SessionContext";
import WorkspacePage from "../pages/WorkspacePage";
import { getStemAudioUrl, getExportFileUrl } from "../api";
import { toFileName, getFriendlySessionCode } from "../utils/formatters";
import { PAGES } from "../constants";

const STEM_ORDER = ["vocals", "drums", "bass", "other"];
const SAVE_DEBOUNCE_MS = 600;

export default function WorkspaceContainer({ setCurrentPage, workspace }) {
  const { currentSession } = useSession();
  const saveTimerRef = useRef(null);

  const job = currentSession.job_id ? currentSession : null;
  const sessionCode = currentSession.session_code || getFriendlySessionCode(currentSession.job_id);

  const stemsList = useMemo(() => {
    if (!job?.stems) return [];
    const entries = Object.entries(job.stems);
    entries.sort(([a], [b]) => STEM_ORDER.indexOf(a) - STEM_ORDER.indexOf(b));
    return entries;
  }, [job]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const handleUpdateMixLevel = (name, value) => {
    // Update local state immediately for responsive UI
    const next = { ...workspace.mixLevels, [name]: value };
    workspace.setMixLevels(next);

    // Debounce the API call so we only save after the user stops moving the fader
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (job?.job_id) {
      saveTimerRef.current = setTimeout(() => {
        workspace.saveMixState(job.job_id, next, workspace.soloStem, workspace.mutedStems, workspace.panLevels);
      }, SAVE_DEBOUNCE_MS);
    }
  };

  const handleUpdatePanLevel = (name, value) => {
    const next = { ...workspace.panLevels, [name]: value };
    workspace.setPanLevels(next);

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (job?.job_id) {
      saveTimerRef.current = setTimeout(() => {
        workspace.saveMixState(job.job_id, workspace.mixLevels, workspace.soloStem, workspace.mutedStems, next);
      }, SAVE_DEBOUNCE_MS);
    }
  };

  const handleToggleMute = (name) => {
    const next = { ...workspace.mutedStems, [name]: !workspace.mutedStems[name] };
    workspace.setMutedStems(next);

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (job?.job_id) {
      saveTimerRef.current = setTimeout(() => {
        workspace.saveMixState(job.job_id, workspace.mixLevels, workspace.soloStem, next, workspace.panLevels);
      }, SAVE_DEBOUNCE_MS);
    }
  };

  const handleToggleSolo = (name) => {
    const next = workspace.soloStem === name ? "" : name;
    workspace.setSoloStem(next);

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (job?.job_id) {
      saveTimerRef.current = setTimeout(() => {
        workspace.saveMixState(job.job_id, workspace.mixLevels, next, workspace.mutedStems, workspace.panLevels);
      }, SAVE_DEBOUNCE_MS);
    }
  };

  const handleResetMix = () => {
    if (job?.job_id) workspace.resetMixState(job.job_id);
  };

  const onCreateStudyMixExport = () => {
    if (job?.job_id) workspace.createExport(job.job_id, "study_mix", "wav");
  };

  const onCreateStemsExport = () => {
    if (job?.job_id) workspace.createExport(job.job_id, "stems", "zip");
  };

  const onCreateCustomExport = () => {
    if (job?.job_id) workspace.createExport(job.job_id, "custom", "wav");
  };

  const onRefreshExports = () => {
    if (job?.job_id) workspace.fetchExports(job.job_id);
  };

  return (
    <WorkspacePage
      key={job?.session_id || job?.id || "empty"}
      job={job}
      sessionCode={sessionCode}
      stemsList={stemsList}
      getStemAudioUrl={getStemAudioUrl}
      mixLevels={workspace.mixLevels}
      updateMixLevel={handleUpdateMixLevel}
      panLevels={workspace.panLevels}
      updatePanLevel={handleUpdatePanLevel}
      soloStem={workspace.soloStem}
      mutedStems={workspace.mutedStems}
      toggleStemMute={handleToggleMute}
      toggleStemSolo={handleToggleSolo}
      onResetMix={handleResetMix}
      mixStateLoading={workspace.mixStateLoading}
      mixStateSaving={workspace.mixStateSaving}
      mixStateError={workspace.mixStateError}
      exportJobs={workspace.exportJobs}
      exportJobsLoading={workspace.exportJobsLoading}
      exportJobsError={workspace.exportJobsError}
      exportActionLoading={workspace.exportActionLoading}
      exportActionMessage={workspace.exportActionMessage}
      onCreateStudyMixExport={onCreateStudyMixExport}
      onCreateStemsExport={onCreateStemsExport}
      onCreateCustomExport={onCreateCustomExport}
      onRetryExport={() => {}}
      onRefreshExports={onRefreshExports}
      getExportFileUrl={getExportFileUrl}
      masterMetrics={job?.master_metrics || null}
      toFileName={toFileName}
      onGoDiscover={() => setCurrentPage(PAGES.discover)}
      onGoLibrary={() => setCurrentPage(PAGES.library)}
      userPresets={workspace.userPresets}
      onApplyPreset={(levels) => workspace.applyPreset(job?.job_id, levels)}
      onSaveUserPreset={(name) => workspace.saveUserPreset(name, workspace.mixLevels)}
      onDeleteUserPreset={workspace.deleteUserPreset}
      drumAnalysis={workspace.drumAnalysis}
      drumAnalysisLoading={workspace.drumAnalysisLoading}
      onTriggerDrumAnalysis={() => workspace.triggerDrumAnalysisAction(job?.job_id)}
      onGoDrumInspector={() => setCurrentPage(PAGES.drum_inspector)}
    />
  );
}

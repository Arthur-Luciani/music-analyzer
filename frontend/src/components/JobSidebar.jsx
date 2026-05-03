import { useProcessingContext } from "../context/ProcessingContext";
import { useSession } from "../context/SessionContext";
import { PAGES } from "../constants";
import { 
  getStateBadgeClass, 
  getStateBadgeLabel, 
  getFriendlySessionCode 
} from "../utils/formatters";

export default function JobSidebar({ setCurrentPage }) {
  const { job, processing, error, isPolling, closeSocket, setProcessing } = useProcessingContext();
  const { hydratSessionAndNavigate } = useSession();

  if (!processing && !job) return null;

  const handleGoWorkspace = async () => {
    if (job?.job_id) {
      await hydratSessionAndNavigate(job.job_id);
      setCurrentPage(PAGES.workspace);
      // We can stop tracking once the user goes to workspace
      closeSocket();
      setProcessing(false);
    }
  };

  const status = job?.state || "queued";
  const progress = job?.progress || 0;
  const title = job?.track_title || "Nova separação";
  const artist = job?.artist || getFriendlySessionCode(job?.job_id);

  return (
    <div className={`job-sidebar-overlay ${processing ? "active" : ""}`}>
      <div className="job-sidebar-card">
        <div className="job-sidebar-header">
          <div className="job-sidebar-title">
            <strong>{title}</strong>
            <span>{artist}</span>
          </div>
          <button 
            className="job-sidebar-close" 
            onClick={() => setProcessing(false)}
            aria-label="Fechar acompanhamento"
          >
            &times;
          </button>
        </div>

        <div className="job-sidebar-body">
          <div className="job-sidebar-status-row">
            <span className={`state ${getStateBadgeClass(status)}`}>
              {getStateBadgeLabel(status)}
            </span>
            {isPolling && <span className="polling-indicator">Sincronizando...</span>}
          </div>

          <div className="job-sidebar-progress">
            <div className="progress-rail">
              <i style={{ width: `${progress}%` }}></i>
            </div>
            <div className="progress-label">{progress}%</div>
          </div>

          {job?.message && <p className="job-sidebar-message">{job.message}</p>}
          {error && <p className="error-banner small">{error}</p>}
        </div>

        <div className="job-sidebar-footer">
          {status === "ready" ? (
            <button className="btn btn-primary btn-full" onClick={handleGoWorkspace}>
              Abrir no Workspace
            </button>
          ) : (
            <p className="job-sidebar-hint">O processo continuará em segundo plano.</p>
          )}
        </div>
      </div>
    </div>
  );
}

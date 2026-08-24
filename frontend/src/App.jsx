import { useState, useEffect } from "react";
import { PAGES } from "./constants";
import { ProcessingProvider } from "./context/ProcessingContext";
import DiscoverContainer from "./containers/DiscoverContainer";
import WorkspaceContainer from "./containers/WorkspaceContainer";
import LibraryContainer from "./containers/LibraryContainer";
import DrumInspectorContainer from "./containers/DrumInspectorContainer";
import JobSidebar from "./components/JobSidebar";
import { useSession } from "./context/SessionContext";
import { useWorkspace } from "./hooks/useWorkspace";

export default function App() {
  const [currentPage, setCurrentPage] = useState(PAGES.discover);
  const [resumeSessionId, setResumeSessionId] = useState(null);
  const { currentSession } = useSession();
  const workspace = useWorkspace();

  const handleResumeDraft = (sessionId) => {
    setResumeSessionId(sessionId);
    setCurrentPage(PAGES.discover);
  };

  useEffect(() => {
    if (currentSession?.job_id) {
      workspace.fetchMixState(currentSession.job_id);
      workspace.fetchExports(currentSession.job_id);
      workspace.fetchDrumAnalysis(currentSession.job_id);
      workspace.fetchMarketMidiStatus(currentSession.job_id);
    }
  }, [currentSession?.job_id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ProcessingProvider>
      <main className={`page-shell ${currentPage === PAGES.workspace || currentPage === PAGES.drum_inspector ? "full-width" : ""} ${currentPage === PAGES.drum_inspector ? "viewport-clamped" : ""}`}>
        <header className="topbar">
          <button className="brand" onClick={() => setCurrentPage(PAGES.discover)}>
            <span className="brand-badge">MX</span>
            <span className="brand-title">
              <strong>Music Analyzer</strong>
              <span>Área de Trabalho</span>
            </span>
          </button>

          <nav className="nav-links">
            <button
              className={`nav-link-btn ${currentPage === PAGES.discover ? "active" : ""}`}
              onClick={() => setCurrentPage(PAGES.discover)}
            >
              Descobrir
            </button>
            <button
              className={`nav-link-btn ${currentPage === PAGES.library ? "active" : ""}`}
              onClick={() => setCurrentPage(PAGES.library)}
            >
              Biblioteca
            </button>
          </nav>
        </header>

        {currentPage === PAGES.discover && (
          <DiscoverContainer
            setCurrentPage={setCurrentPage}
            workspace={workspace}
            resumeSessionId={resumeSessionId}
            onResumeHandled={() => setResumeSessionId(null)}
          />
        )}
        {currentPage === PAGES.workspace && <WorkspaceContainer setCurrentPage={setCurrentPage} workspace={workspace} />}
        {currentPage === PAGES.library && (
          <LibraryContainer setCurrentPage={setCurrentPage} workspace={workspace} onResumeDraft={handleResumeDraft} />
        )}
        {currentPage === PAGES.drum_inspector && (
          <DrumInspectorContainer 
            session={currentSession}
            workspace={workspace}
            onBack={() => setCurrentPage(PAGES.workspace)}
          />
        )}

        <JobSidebar setCurrentPage={setCurrentPage} />
      </main>
    </ProcessingProvider>
  );
}

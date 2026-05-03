import { createContext, useContext, useMemo, useState, useCallback } from "react";
import { getSession } from "../api";

const EMPTY_SESSION = {
  session_id: "",
  session_code: "",
  job_id: "",
  status: "idle",
};

const SessionContext = createContext(null);

function buildSessionSnapshot(payload, previous) {
  // Normalise: some endpoints use "state", others use "status" for the same concept
  const resolvedState = payload?.state ?? payload?.status ?? previous.state ?? previous.status;

  return {
    session_id: payload?.session_id ?? previous.session_id,
    session_code: payload?.session_code ?? previous.session_code,
    // job_id may come from payload.job_id, or fall back to session_id
    job_id: payload?.job_id ?? payload?.session_id ?? previous.job_id,
    // Keep both aliases in sync so components can read either field
    status: resolvedState,
    state: resolvedState,
    // Preserve extra fields (stems, selected_track, separation_device, etc.)
    ...Object.fromEntries(
      Object.entries(payload || {}).filter(
        ([k]) => !["session_id", "session_code", "job_id", "state", "status"].includes(k)
      )
    ),
  };
}

export function SessionProvider({ children }) {
  const [currentSession, setCurrentSession] = useState(EMPTY_SESSION);

  const setSessionFromPayload = useCallback((payload) => {
    setCurrentSession((previous) => buildSessionSnapshot(payload, previous));
  }, []);

  const clearSession = useCallback(() => {
    setCurrentSession(EMPTY_SESSION);
  }, []);

  const hydratSessionAndNavigate = useCallback(async (sessionId) => {
    if (!sessionId) return;
    try {
      const detail = await getSession(sessionId);
      setCurrentSession((previous) => buildSessionSnapshot(detail, previous));
    } catch {
      // Swallow error — caller can handle navigation fallback if needed
    }
  }, []);

  const value = useMemo(
    () => ({
      currentSession,
      setSessionFromPayload,
      clearSession,
      hydratSessionAndNavigate,
    }),
    [currentSession, setSessionFromPayload, clearSession, hydratSessionAndNavigate]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}

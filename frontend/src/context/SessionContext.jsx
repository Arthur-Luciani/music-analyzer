import { createContext, useContext, useMemo, useState } from "react";

const EMPTY_SESSION = {
  session_id: "",
  session_code: "",
  job_id: "",
  status: "idle",
};

const SessionContext = createContext(null);

function buildSessionSnapshot(payload, previous) {
  return {
    session_id: payload?.session_id ?? previous.session_id,
    session_code: payload?.session_code ?? previous.session_code,
    job_id: payload?.job_id ?? previous.job_id,
    status: payload?.state ?? payload?.status ?? previous.status,
  };
}

export function SessionProvider({ children }) {
  const [currentSession, setCurrentSession] = useState(EMPTY_SESSION);

  const value = useMemo(
    () => ({
      currentSession,
      setSessionFromPayload(payload) {
        setCurrentSession((previous) => buildSessionSnapshot(payload, previous));
      },
      clearSession() {
        setCurrentSession(EMPTY_SESSION);
      },
    }),
    [currentSession]
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

import { useState } from "react";
import { getSession, getSessionEvents } from "../api";

/**
 * useSessionEvents: manages per-session event log and hydration from the API.
 * Named separately from the context-level `useSession` (SessionContext.jsx).
 */
export function useSessionEvents() {
  const [sessionEvents, setSessionEvents] = useState([]);
  const [sessionEventsLoading, setSessionEventsLoading] = useState(false);
  const [sessionEventsError, setSessionEventsError] = useState("");

  const fetchSessionEvents = async (sessionId, options = {}) => {
    const { silent = false } = options;
    if (!sessionId) return;

    if (!silent) setSessionEventsLoading(true);
    setSessionEventsError("");

    try {
      const events = await getSessionEvents(sessionId);
      setSessionEvents(Array.isArray(events) ? events : []);
    } catch (err) {
      setSessionEventsError(err.message || "Falha ao carregar eventos");
    } finally {
      if (!silent) setSessionEventsLoading(false);
    }
  };

  const hydrateSessionEvents = async (sessionId) => {
    await fetchSessionEvents(sessionId);
  };

  return {
    sessionEvents,
    sessionEventsLoading,
    sessionEventsError,
    fetchSessionEvents,
    hydrateSessionEvents,
  };
}

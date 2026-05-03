import { useState, useRef, useEffect, useCallback } from "react";
import { connectJobSocket, getSession } from "../api";

const FINAL_STATES = new Set(["ready", "failed"]);
const POLLING_INTERVAL = 3000;

export function useProcessing() {
  const [processing, setProcessing] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [isPolling, setIsPolling] = useState(false);
  const [trackingId, setTrackingId] = useState(null);
  
  const jobSocketRef = useRef(null);
  const pollingTimerRef = useRef(null);
  const jobRef = useRef(null);

  // Sync ref with state so callbacks always see latest
  useEffect(() => {
    jobRef.current = job;
  }, [job]);

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const closeSocket = useCallback(() => {
    if (jobSocketRef.current) {
      jobSocketRef.current.close();
      jobSocketRef.current = null;
    }
  }, []);

  const startPolling = useCallback((jobId) => {
    if (pollingTimerRef.current) return;
    
    console.log(`[useProcessing] Starting polling for ${jobId}`);
    setIsPolling(true);
    
    pollingTimerRef.current = setInterval(async () => {
      try {
        const data = await getSession(jobId);
        console.log(`[useProcessing] Polling update for ${jobId}: ${data.state}`);
        setJob(data);
        setError("");
        
        if (FINAL_STATES.has(data.state)) {
          console.log(`[useProcessing] Job ${jobId} finished via polling`);
          stopPolling();
          setProcessing(false);
        }
      } catch (err) {
        console.error("[useProcessing] Polling error:", err);
        setError("Falha ao sincronizar progresso (polling)");
      }
    }, POLLING_INTERVAL);
  }, [stopPolling]);

  const startTracking = useCallback((jobId) => {
    if (!jobId) return;

    console.log(`[useProcessing] Starting tracking for ${jobId}`);
    setTrackingId(jobId);
    closeSocket();
    stopPolling();
    setError("");
    setProcessing(true);
    // Note: we don't clear job state here to avoid UI flickering if we already have data

    jobSocketRef.current = connectJobSocket(
      jobId,
      (payload) => {
        console.log(`[useProcessing] WS message for ${jobId}: ${payload.state}`);
        setJob(payload);
        if (FINAL_STATES.has(payload.state)) {
          console.log(`[useProcessing] Job ${jobId} finished via WS`);
          closeSocket();
          setProcessing(false);
        }
      },
      () => {
        console.warn(`[useProcessing] WS error for ${jobId}. Switching to polling.`);
        closeSocket();
        startPolling(jobId);
      },
      (event) => {
        // Use the ref to get the latest state inside the closure
        const currentState = jobRef.current?.state;
        if (!FINAL_STATES.has(currentState) && event.code !== 1000) {
          console.warn(`[useProcessing] WS closed unexpectedly (code ${event.code}) for ${jobId}. Switching to polling.`);
          startPolling(jobId);
        }
      },
      () => {
        console.log(`[useProcessing] WS connected for ${jobId}`);
        setError(""); // Clear error on successful connection
      }
    );
  }, [closeSocket, startPolling, stopPolling]);

  useEffect(() => {
    return () => {
      closeSocket();
      stopPolling();
    };
  }, [closeSocket, stopPolling]);

  return {
    processing,
    setProcessing,
    job,
    setJob,
    error,
    setError,
    startTracking,
    closeSocket,
    isPolling,
    trackingId,
  };
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (response.ok) {
    return payload;
  }

  const detail = typeof payload === "object" && payload !== null ? payload.detail ?? payload : payload;
  const message =
    (typeof detail === "object" && detail !== null && detail.message) ||
    (typeof detail === "string" ? detail : "Request failed");

  const error = new Error(message);
  error.status = response.status;
  error.code = typeof detail === "object" && detail !== null ? detail.code : undefined;
  throw error;
}

export async function searchCandidates(query, limit = 5) {
  const response = await fetch(
    `/api/search?query=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`
  );
  return parseResponse(response);
}

export async function createProcessJob(query, selectedSourceId, targetStems) {
  const payload = { query };
  if (selectedSourceId) {
    payload.selected_source_id = selectedSourceId;
  }
  if (Array.isArray(targetStems) && targetStems.length > 0) {
    payload.target_stems = targetStems;
  }

  const response = await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseResponse(response);
}

export async function listSessions(filters = {}) {
  const params = new URLSearchParams();
  if (filters.query) {
    params.set("query", filters.query);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.created_from) {
    params.set("created_from", filters.created_from);
  }
  if (filters.created_to) {
    params.set("created_to", filters.created_to);
  }
  params.set("page", String(filters.page || 1));
  params.set("page_size", String(filters.page_size || 20));

  const response = await fetch(`/api/sessions?${params.toString()}`);
  return parseResponse(response);
}

export async function getSession(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
  return parseResponse(response);
}

export async function duplicateSession(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/duplicate`, {
    method: "POST",
  });
  return parseResponse(response);
}

export async function reprocessSession(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/reprocess`, {
    method: "POST",
  });
  return parseResponse(response);
}

export async function getSessionEvents(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/events`);
  return parseResponse(response);
}

export async function getMixState(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/mix-state`);
  return parseResponse(response);
}

export async function updateMixState(sessionId, payload) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/mix-state`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function createExportJob(sessionId, payload) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function listExportJobs(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/exports`);
  return parseResponse(response);
}

export async function getExportJob(sessionId, exportId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/exports/${encodeURIComponent(exportId)}`
  );
  return parseResponse(response);
}

export function getExportFileUrl(sessionId, exportId, fileName) {
  return `/api/sessions/${encodeURIComponent(sessionId)}/exports/${encodeURIComponent(
    exportId
  )}/files/${encodeURIComponent(fileName)}`;
}

export function getStemAudioUrl(jobId, stemName) {
  return `/api/jobs/${encodeURIComponent(jobId)}/stems/${encodeURIComponent(stemName)}.wav`;
}

export function connectJobSocket(jobId, onMessage, onError) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/${jobId}`);

  socket.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };

  socket.onerror = () => {
    onError?.(new Error("WebSocket connection error"));
  };

  return socket;
}

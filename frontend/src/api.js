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
  error.candidates = typeof detail === "object" && detail !== null ? detail.candidates || [] : [];
  error.recommendedSourceId =
    typeof detail === "object" && detail !== null ? detail.recommended_source_id : undefined;
  throw error;
}

export async function searchCandidates(query, limit = 5) {
  const response = await fetch(
    `/api/search?query=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`
  );
  return parseResponse(response);
}

export async function createProcessJob(query, selectedSourceId) {
  const payload = { query };
  if (selectedSourceId) {
    payload.selected_source_id = selectedSourceId;
  }

  const response = await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseResponse(response);
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

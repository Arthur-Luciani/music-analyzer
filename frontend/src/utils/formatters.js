export function getFriendlySessionCode(jobId) {
  if (!jobId) {
    return "MX-000";
  }

  const seed = Array.from(jobId).reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const serial = (seed % 999) + 1;
  return `MX-${String(serial).padStart(3, "0")}`;
}

export function getStateBadgeLabel(state) {
  if (state === "ready") {
    return "Pronta";
  }
  if (state === "failed") {
    return "Falhou";
  }
  if (state === "separating") {
    return "Separando";
  }
  if (state === "downloading") {
    return "Baixando";
  }
  return "Na fila";
}

export function getStateBadgeClass(state) {
  if (state === "ready") {
    return "ready";
  }
  if (state === "failed") {
    return "failed";
  }
  if (state === "separating") {
    return "processing";
  }
  if (state === "downloading") {
    return "download";
  }
  return "processing";
}

export function toFileName(pathLike) {
  if (!pathLike || typeof pathLike !== "string") {
    return "arquivo.wav";
  }
  const normalized = pathLike.replace(/\\/g, "/");
  const chunks = normalized.split("/");
  return chunks[chunks.length - 1] || "arquivo.wav";
}

export function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

export function formatBytes(sizeInBytes) {
  if (!sizeInBytes || sizeInBytes <= 0) {
    return "--";
  }

  const megaBytes = sizeInBytes / (1024 * 1024);
  return `${megaBytes.toFixed(1)} MB`;
}

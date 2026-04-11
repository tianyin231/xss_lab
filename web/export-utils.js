export function buildExportUrl(apiBase, jobId, format = 'html') {
  return `${apiBase}/jobs/${jobId}/export?format=${encodeURIComponent(format)}`
}

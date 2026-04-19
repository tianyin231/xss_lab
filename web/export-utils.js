export function buildExportUrl(apiBase, jobId, format = 'html', authToken = '') {
  const params = new URLSearchParams()
  params.set('format', format)
  if (authToken) params.set('auth_token', authToken)
  return `${apiBase}/jobs/${jobId}/export?${params.toString()}`
}

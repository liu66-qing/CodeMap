const BASE_URL = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  // Documents
  uploadDocument: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE_URL}/documents`, { method: 'POST', body: formData })
    return res.json()
  },
  listDocuments: () => request<any[]>('/documents'),

  // Query
  query: (question: string, includeReasoning = true) =>
    request<any>('/query', {
      method: 'POST',
      body: JSON.stringify({ question, include_reasoning: includeReasoning }),
    }),

  // Graph
  searchEntities: (q: string) => request<any[]>(`/graph/entities?q=${encodeURIComponent(q)}`),
  getNeighborhood: (entityId: string, hops = 2) =>
    request<any>(`/graph/entities/${entityId}/neighborhood?hops=${hops}`),
  getGraphStats: () => request<any>('/graph/stats'),

  // Conflicts
  listConflicts: () => request<any>('/conflicts'),
  resolveConflict: (id: string, resolution: string, note?: string) =>
    request<any>(`/conflicts/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution, note }),
    }),

  // Timeline
  getEntityTimeline: (entityId: string) => request<any>(`/timeline/entity/${entityId}`),
  getSnapshot: (timestamp: string) =>
    request<any>(`/timeline/snapshot?timestamp=${encodeURIComponent(timestamp)}`),
  getDiff: (from: string, to: string) =>
    request<any>(`/timeline/diff?from_ts=${encodeURIComponent(from)}&to_ts=${encodeURIComponent(to)}`),

  // Admin
  healthCheck: () => request<any>('/admin/health'),
}

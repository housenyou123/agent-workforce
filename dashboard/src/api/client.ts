const API_BASE = import.meta.env.VITE_API_URL || 'http://118.196.147.14/aw';

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  // Dashboard
  stats: (days = 7) => fetchJSON<any[]>(`/api/stats?days=${days}`),

  // Activity
  activity: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON<any[]>(`/api/activity?${qs}`);
  },
  activityGrouped: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON<any[]>(`/api/activity/grouped?${qs}`);
  },

  // Agents
  agents: () => fetchJSON<any[]>('/api/agents'),
  agent: (id: string) => fetchJSON<any>(`/api/agents/${id}`),

  // Skills
  skills: () => fetchJSON<any[]>('/api/skills'),
  createSkill: (data: any) => fetchJSON<any>('/api/skills', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }),
  updateSkill: (id: string, data: any) => fetchJSON<any>(`/api/skills/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }),
  deleteSkill: (id: string) => fetchJSON<any>(`/api/skills/${id}`, { method: 'DELETE' }),

  // Memory
  searchMemory: (q: string, project?: string) => {
    const params = new URLSearchParams({ q });
    if (project) params.set('project', project);
    return fetchJSON<any[]>(`/api/memory/search?${params}`);
  },
  recallMemory: (project?: string, agent?: string) => {
    const params = new URLSearchParams();
    if (project) params.set('project', project);
    if (agent) params.set('agent', agent);
    return fetchJSON<any[]>(`/api/memory/recall?${params}`);
  },
  memoryStats: () => fetchJSON<any>('/api/memory/stats'),

  // Traces
  traces: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON<any[]>(`/api/traces?${qs}`);
  },
  traceDetail: (traceId: string) => fetchJSON<any>(`/api/traces/${traceId}`),
};

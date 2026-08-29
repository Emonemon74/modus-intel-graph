const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

async function req(path, opts) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}

export const api = {
  stats: () => req('/stats'),
  jobs: () => req('/jobs'),
  listNodes: (type) => req(`/nodes/${type}`),
  nodeDetail: (type, id) => req(`/nodes/${type}/${id}`),
  graph: (type, id, depth = 1) =>
    req(`/graph?focus_type=${type}&focus_id=${id}&depth=${depth}`),
  evidence: (claimType, id) => req(`/evidence/${claimType}/${id}`),
  ingest: (industry) =>
    req('/ingest', { method: 'POST', body: JSON.stringify({ industry }) }),
  addEntity: (type, name, context) =>
    req('/entities', {
      method: 'POST',
      body: JSON.stringify({ type, name, context }),
    }),
  cascade: (trigger_type, trigger_id, hypothesis, max_depth) =>
    req('/cascade', {
      method: 'POST',
      body: JSON.stringify({ trigger_type, trigger_id, hypothesis, max_depth }),
    }),
  cascadeResult: (runId) => req(`/cascade/${runId}`),
  cascadeList: () => req('/cascades'),
}

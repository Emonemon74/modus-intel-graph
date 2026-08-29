import { useEffect, useState } from 'react'
import { api } from './api'
import GraphView from './GraphView'
import './App.css'

const NODE_TYPES = ['stage', 'process', 'activity', 'role', 'skill']

export default function App() {
  const [tab, setTab] = useState('explorer')
  const [stats, setStats] = useState(null)

  const refreshStats = () => api.stats().then(setStats).catch(() => {})
  useEffect(() => { refreshStats() }, [])

  return (
    <div className="app">
      <header>
        <h1>Process × Role × Skill Intelligence Graph</h1>
        <nav>
          {['explorer', 'cascade', 'add', 'jobs'].map((t) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
        {stats && (
          <div className="stats">
            {Object.entries(stats.counts).map(([k, v]) => (
              <span key={k}><b>{v}</b> {k}</span>
            ))}
          </div>
        )}
      </header>
      <main>
        {tab === 'explorer' && <Explorer />}
        {tab === 'cascade' && <Cascade />}
        {tab === 'add' && <AddEntity onDone={refreshStats} />}
        {tab === 'jobs' && <Jobs />}
      </main>
    </div>
  )
}

// --------------------------------------------------------------------------- //
function Explorer() {
  const [type, setType] = useState('process')
  const [nodes, setNodes] = useState([])
  const [sel, setSel] = useState(null)          // {type, id}
  const [detail, setDetail] = useState(null)
  const [graph, setGraph] = useState(null)
  const [depth, setDepth] = useState(2)

  useEffect(() => { api.listNodes(type).then(setNodes) }, [type])
  useEffect(() => {
    if (!sel) return
    api.nodeDetail(sel.type, sel.id).then(setDetail)
    api.graph(sel.type, sel.id, depth).then(setGraph)
  }, [sel, depth])

  return (
    <div className="explorer">
      <aside className="list">
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {NODE_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <ul>
          {nodes.map((n) => (
            <li key={n.id} className={sel?.id === n.id && sel?.type === type ? 'on' : ''}
                onClick={() => setSel({ type, id: n.id })}>
              {n.label}
            </li>
          ))}
        </ul>
      </aside>

      <div className="canvas-wrap">
        {graph
          ? <GraphView data={graph} highlight={[`${sel.type}:${sel.id}`]}
                       onSelect={(t, id) => setSel({ type: t, id })} />
          : <p className="hint">Pick a node to explore its neighbourhood.</p>}
        <label className="depth">depth
          <input type="range" min="1" max="3" value={depth}
                 onChange={(e) => setDepth(+e.target.value)} /> {depth}
        </label>
      </div>

      {detail && <EntityPanel detail={detail} onNav={(t, id) => setSel({ type: t, id })} />}
    </div>
  )
}

// --------------------------------------------------------------------------- //
function EntityPanel({ detail, onNav }) {
  const [evidence, setEvidence] = useState(null)
  const n = detail.node
  const opp = detail.ai_opportunity
  const si = detail.skill_impact
  const ri = detail.role_impact
  const pi = detail.process_impact
  const affectedRoles = detail.affected_roles

  const showEvidence = (claimType, id) =>
    api.evidence(claimType, id).then(setEvidence)

  return (
    <aside className="panel">
      <h2>{n.name} <small>{detail.type}</small></h2>
      {n.description && <p>{n.description}</p>}
      {n.purpose && <p><i>{n.purpose}</i></p>}
      {n.automation_potential && <p>Automation potential: <b>{n.automation_potential}</b></p>}

      {opp && (
        <div className="overlay">
          <h3>AI Opportunity <span className={`tag ${opp.automation_type}`}>{opp.automation_type}</span></h3>
          <p>{opp.summary}</p>
          <p><b>Capability:</b> {opp.ai_capability}</p>
          <p><b>Benefit:</b> {opp.benefit}</p>
          <p><b>Risk:</b> {opp.risk}</p>
          <p><b>Confidence:</b> {opp.confidence}</p>
          <p className="rationale">{opp.rationale}</p>
          <button onClick={() => showEvidence('ai_opportunity', opp.id)}>Show evidence</button>
        </div>
      )}

      {si && (
        <div className="overlay">
          <h3>Skill Impact <span className="tag">{si.classification}</span></h3>
          <p>{si.rationale}</p>
          <p><b>Confidence:</b> {si.confidence}</p>
          <button onClick={() => showEvidence('skill_impact', si.id)}>Show evidence</button>
        </div>
      )}

      {ri && (
        <div className="overlay">
          <h3>Future Change <span className="tag">{ri.exposure_band} exposure</span></h3>
          <p>{ri.headline}</p>
          <p><b>AI exposure:</b> {ri.ai_exposure} · <b>Skill pressure:</b> {ri.skill_pressure}</p>
          <p><b>Activities:</b> {JSON.stringify(ri.activity_breakdown)}</p>
          <p><b>Skills:</b> {JSON.stringify(ri.skill_breakdown)}</p>
          <p className="rationale">derived: {ri.derived_from}</p>
        </div>
      )}

      {pi && (
        <div className="overlay">
          <h3>Process AI Roll-up</h3>
          <p><b>AI-opportunity score:</b> {pi.ai_opportunity_score} ({pi.activities_total} activities)</p>
          <p><b>Breakdown:</b> {JSON.stringify(pi.activity_breakdown)}</p>
          {affectedRoles?.length > 0 && (
            <>
              <p><b>Affected roles ({affectedRoles.length}):</b></p>
              <ul>
                {affectedRoles.map((r) => (
                  <li key={r.id} onClick={() => onNav('role', r.id)}>→ {r.label}</li>
                ))}
              </ul>
            </>
          )}
          <p className="rationale">derived: {pi.derived_from}</p>
        </div>
      )}

      {Object.entries(detail.neighbours).map(([rel, items]) => (
        <div key={rel} className="rel">
          <h4>{rel} ({items.length})</h4>
          <ul>
            {items.map((it, i) => (
              <li key={i} onClick={() => onNav(it.type, it.id)}>
                {it.direction === 'in' ? '← ' : '→ '}{it.label} <small>{it.type}</small>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {evidence && (
        <div className="evidence" onClick={() => setEvidence(null)}>
          <h4>Evidence ({evidence.length}) — click to close</h4>
          {evidence.map((e, i) => (
            <div key={i} className="ev">
              <div className="score">{e.relevance.toFixed(2)}</div>
              <div>
                <p>{e.quote}</p>
                {e.source && <small>{e.source.kind} · {e.source.title} {e.source.url}</small>}
              </div>
            </div>
          ))}
          {!evidence.length && <p>No stored evidence — this finding was reasoned from domain knowledge.</p>}
        </div>
      )}
    </aside>
  )
}

// --------------------------------------------------------------------------- //
function Cascade() {
  const [type, setType] = useState('activity')
  const [nodes, setNodes] = useState([])
  const [id, setId] = useState(null)
  const [hyp, setHyp] = useState('AI fully automates this activity')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => { api.listNodes(type).then(setNodes) }, [type])

  const run = async () => {
    setBusy(true); setResult(null)
    try {
      const { run_id } = await api.cascade(type, Number(id), hyp)
      setResult(await api.cascadeResult(run_id))
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="cascade">
      <div className="controls">
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {['activity', 'role', 'skill', 'process'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <select value={id ?? ''} onChange={(e) => setId(e.target.value)}>
          <option value="">— pick —</option>
          {nodes.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
        </select>
        <input value={hyp} onChange={(e) => setHyp(e.target.value)} placeholder="hypothesis" />
        <button disabled={!id || busy} onClick={run}>{busy ? 'reasoning…' : 'Run cascade'}</button>
      </div>

      {result && (
        <div className="results">
          <h3>“{result.hypothesis}”</h3>
          {result.results.length === 0 && <p>No material downstream impact found.</p>}
          {result.results.map((r, i) => (
            <div key={i} className="impact" style={{ marginLeft: (r.depth - 1) * 20 }}>
              <span className="d">d{r.depth}</span>
              <div>
                <b>{r.label}</b> <small>{r.affected_type}</small>
                <p>{r.effect}</p>
                <p className="reason">{r.reasoning}</p>
                <small className="path">{r.path.join('  →  ')}</small>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
function AddEntity({ onDone }) {
  const [type, setType] = useState('process')
  const [name, setName] = useState('')
  const [context, setContext] = useState('')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState(null)

  const submit = async () => {
    setBusy(true); setOut(null)
    try {
      const r = await api.addEntity(type, name, context)
      setOut(r); onDone?.()
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="add">
      <p className="hint">The “surprise record” test: add a {type} that isn’t in the graph.
        The same pipeline that built the seed graph analyses it live.</p>
      <select value={type} onChange={(e) => setType(e.target.value)}>
        {['process', 'role', 'skill'].map((t) => <option key={t}>{t}</option>)}
      </select>
      <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
      <textarea placeholder="optional context" value={context}
                onChange={(e) => setContext(e.target.value)} />
      <button disabled={!name || busy} onClick={submit}>
        {busy ? 'analysing… (30–60s)' : 'Add & analyse'}
      </button>
      {out && <pre>{JSON.stringify(out, null, 2)}</pre>}
    </div>
  )
}

// --------------------------------------------------------------------------- //
function Jobs() {
  const [jobs, setJobs] = useState([])
  useEffect(() => {
    const f = () => api.jobs().then(setJobs)
    f(); const t = setInterval(f, 2000); return () => clearInterval(t)
  }, [])
  return (
    <table className="jobs">
      <thead><tr><th>id</th><th>kind</th><th>target</th><th>step</th><th>status</th><th>detail</th></tr></thead>
      <tbody>
        {jobs.map((j) => (
          <tr key={j.id} className={j.status}>
            <td>{j.id}</td><td>{j.kind}</td><td>{j.target}</td>
            <td>{j.step}</td><td>{j.status}</td><td>{j.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'

const COLORS = {
  industry: '#6366f1', stage: '#0ea5e9', process: '#10b981',
  activity: '#f59e0b', role: '#ef4444', skill: '#a855f7',
}

export default function GraphView({ data, highlight = [], onSelect }) {
  const boxRef = useRef(null)

  useEffect(() => {
    if (!boxRef.current) return
    const cy = cytoscape({
      container: boxRef.current,
      elements: [
        ...data.nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type } })),
        ...data.links.map((l) => ({
          data: {
            id: `${l.source}->${l.target}:${l.relation}`,
            source: l.source, target: l.target, label: l.relation.replace(/_/g, ' ').toLowerCase(),
          },
        })),
      ],
      style: [
        { selector: 'node', style: {
            'background-color': (e) => COLORS[e.data('type')] || '#888',
            label: 'data(label)', color: '#cbd5e1', 'font-size': 9,
            'text-wrap': 'wrap', 'text-max-width': 80, 'text-valign': 'bottom',
            'text-margin-y': 2, 'text-background-color': '#0f172a',
            'text-background-opacity': 0.7, 'text-background-padding': 2,
            width: 22, height: 22,
          } },
        { selector: 'node.hl', style: {
            'border-width': 4, 'border-color': '#fde047', width: 32, height: 32,
            'font-size': 11, color: '#fff', 'z-index': 99,
          } },
        { selector: 'edge', style: {
            width: 1.2, 'line-color': '#475569', 'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle', 'arrow-scale': 0.7, 'curve-style': 'bezier',
            label: 'data(label)', 'font-size': 6.5, color: '#64748b',
            'text-rotation': 'autorotate',
          } },
      ],
      layout: {
        name: 'cose', animate: false, nodeRepulsion: 20000,
        idealEdgeLength: 120, nodeOverlap: 20, gravity: 0.25, padding: 40,
        fit: true,
      },
    })
    cy.ready(() => cy.fit(undefined, 40))
    highlight.forEach((h) => cy.getElementById(h).addClass('hl'))
    cy.on('tap', 'node', (evt) => {
      const [type, id] = evt.target.id().split(':')
      onSelect?.(type, Number(id))
    })
    return () => cy.destroy()
  }, [data, highlight])

  return (
    <>
      <div ref={boxRef} className="graph-canvas" />
      <div className="legend">
        {Object.entries(COLORS).map(([k, c]) => (
          <span key={k}><i style={{ background: c }} />{k}</span>
        ))}
      </div>
    </>
  )
}

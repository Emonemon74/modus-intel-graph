"""Reading the graph.

The whole point of the single `edges` table: one function returns the
neighbours of ANY node, and the cascade reasoner + the UI both build on it.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Edge, NODE_MODELS


def get_node(s: Session, node_type: str, node_id: int):
    return s.get(NODE_MODELS[node_type], node_id)


def node_label(obj) -> str:
    return getattr(obj, "name", f"#{obj.id}")


def neighbours(s: Session, node_type: str, node_id: int, relations: list[str] | None = None):
    """Return [(relation, direction, neighbour_type, neighbour_id, edge), ...].

    Edges are treated as traversable both ways: a role PERFORMS an activity, and
    from the activity we can walk back to the role.
    """
    q = select(Edge).where(
        or_(
            (Edge.source_type == node_type) & (Edge.source_id == node_id),
            (Edge.target_type == node_type) & (Edge.target_id == node_id),
        )
    )
    if relations:
        q = q.where(Edge.relation.in_(relations))

    out = []
    for e in s.scalars(q):
        if e.source_type == node_type and e.source_id == node_id:
            out.append((e.relation, "out", e.target_type, e.target_id, e))
        else:
            out.append((e.relation, "in", e.source_type, e.source_id, e))
    return out


def subgraph(s: Session, node_type: str, node_id: int, depth: int = 1) -> dict:
    """Breadth-first expansion around a focus node -- feeds the UI graph view."""
    seen: set[tuple[str, int]] = {(node_type, node_id)}
    frontier = [(node_type, node_id)]
    nodes, links = [], []

    def add_node(t, i):
        obj = get_node(s, t, i)
        if obj is not None:
            nodes.append({"id": f"{t}:{i}", "type": t, "label": node_label(obj)})

    add_node(node_type, node_id)
    for _ in range(depth):
        nxt = []
        for t, i in frontier:
            for rel, direction, nt, ni, _e in neighbours(s, t, i):
                links.append({
                    "source": f"{t}:{i}" if direction == "out" else f"{nt}:{ni}",
                    "target": f"{nt}:{ni}" if direction == "out" else f"{t}:{i}",
                    "relation": rel,
                })
                if (nt, ni) not in seen:
                    seen.add((nt, ni))
                    add_node(nt, ni)
                    nxt.append((nt, ni))
        frontier = nxt
    return {"nodes": nodes, "links": links}

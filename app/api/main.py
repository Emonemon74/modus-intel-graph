"""FastAPI application -- the APPLICATION/API layer of the mandatory architecture.

Thin on purpose: every route delegates to the pipeline / graph modules. The UI
talks only to this.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import init_db, session_scope
from app.graph.traverse import get_node, neighbours, node_label, subgraph
from app.models import (
    Activity, AIOpportunity, ClaimEvidence, Edge, Industry, Job, NODE_MODELS,
    Process, Role, Skill, SkillImpact, Source,
)

app = FastAPI(title="Process x Role x Skill Intelligence Graph")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------- #
# Ingest / live add                                                           #
# --------------------------------------------------------------------------- #
class IngestIn(BaseModel):
    industry: str


@app.post("/ingest")
def ingest(body: IngestIn):
    from app.pipeline.ingest import run_ingest

    job_id = run_ingest(body.industry)
    return {"job_id": job_id, "status": "done"}


class EntityIn(BaseModel):
    type: str          # process | role | skill
    name: str
    context: str = ""


@app.post("/entities")
def add_entity(body: EntityIn):
    from app.pipeline.add_entity import DISPATCH

    if body.type not in DISPATCH:
        raise HTTPException(400, f"type must be one of {list(DISPATCH)}")
    created = DISPATCH[body.type](body.name, body.context)
    return {"created": created}


@app.get("/jobs")
def jobs():
    with session_scope() as s:
        rows = s.scalars(select(Job).order_by(Job.id.desc()).limit(20)).all()
        return [{"id": j.id, "kind": j.kind, "target": j.target, "step": j.step,
                 "status": j.status, "detail": j.detail} for j in rows]


# --------------------------------------------------------------------------- #
# Graph read                                                                  #
# --------------------------------------------------------------------------- #
@app.get("/stats")
def stats():
    with session_scope() as s:
        counts = {label: s.scalar(select(func.count()).select_from(m))
                  for label, m in [("industries", Industry), ("processes", Process),
                                   ("activities", Activity), ("roles", Role),
                                   ("skills", Skill), ("edges", Edge), ("sources", Source)]}
        by_rel = dict(s.execute(select(Edge.relation, func.count()).group_by(Edge.relation)).all())
        return {"counts": counts, "edges_by_relation": by_rel}


@app.get("/nodes/{node_type}")
def list_nodes(node_type: str):
    if node_type not in NODE_MODELS:
        raise HTTPException(404, "unknown node type")
    with session_scope() as s:
        rows = s.scalars(select(NODE_MODELS[node_type])).all()
        return [{"id": r.id, "label": node_label(r)} for r in rows]


def _overlay(s, node_type: str, node_id: int) -> dict:
    if node_type == "activity":
        opp = s.scalars(select(AIOpportunity).filter_by(activity_id=node_id)).first()
        return {"ai_opportunity": _as_dict(opp)} if opp else {}
    if node_type == "skill":
        si = s.scalars(select(SkillImpact).filter_by(skill_id=node_id)).first()
        return {"skill_impact": _as_dict(si)} if si else {}
    return {}


def _as_dict(obj) -> dict | None:
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@app.get("/nodes/{node_type}/{node_id}")
def node_detail(node_type: str, node_id: int):
    if node_type not in NODE_MODELS:
        raise HTTPException(404, "unknown node type")
    with session_scope() as s:
        obj = get_node(s, node_type, node_id)
        if obj is None:
            raise HTTPException(404, "not found")
        nbrs: dict[str, list] = {}
        for rel, direction, nt, ni, _e in neighbours(s, node_type, node_id):
            tgt = get_node(s, nt, ni)
            if tgt is None:
                continue
            nbrs.setdefault(rel, []).append({"type": nt, "id": ni, "label": node_label(tgt),
                                             "direction": direction})
        return {"node": _as_dict(obj), "type": node_type,
                "neighbours": nbrs, **_overlay(s, node_type, node_id)}


@app.get("/graph")
def graph(focus_type: str, focus_id: int, depth: int = 1):
    with session_scope() as s:
        if get_node(s, focus_type, focus_id) is None:
            raise HTTPException(404, "focus node not found")
        return subgraph(s, focus_type, focus_id, depth)


@app.get("/evidence/{claim_type}/{claim_id}")
def evidence(claim_type: str, claim_id: int):
    with session_scope() as s:
        rows = s.scalars(
            select(ClaimEvidence).filter_by(claim_type=claim_type, claim_id=claim_id)
            .order_by(ClaimEvidence.relevance.desc())
        ).all()
        out = []
        for ce in rows:
            src = s.get(Source, ce.source_id)
            out.append({"quote": ce.quote, "relevance": ce.relevance,
                        "source": {"title": src.title, "url": src.url,
                                   "publisher": src.publisher, "kind": src.kind} if src else None})
        return out


# --------------------------------------------------------------------------- #
# Cascade                                                                     #
# --------------------------------------------------------------------------- #
class CascadeIn(BaseModel):
    trigger_type: str
    trigger_id: int
    hypothesis: str


@app.post("/cascade")
def cascade(body: CascadeIn):
    from app.pipeline.cascade import run_cascade

    run_id = run_cascade(body.trigger_type, body.trigger_id, body.hypothesis)
    return {"run_id": run_id}


@app.get("/cascade/{run_id}")
def cascade_result(run_id: int):
    from app.pipeline.cascade import get_cascade

    return get_cascade(run_id)


# Serve the built UI (web/dist) if present -- keeps everything one origin.
import os  # noqa: E402

if os.path.isdir("web/dist"):
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="ui")

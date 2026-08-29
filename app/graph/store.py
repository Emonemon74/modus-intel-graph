"""Idempotent writes to the graph.

Every pipeline step calls these. "Idempotent" = running ingest twice does not
create duplicate nodes or edges. That property is what makes the pipeline
*resumable* and what makes the live "surprise record" test safe to re-run.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import embed
from app.models import Edge, NODE_MODELS, Skill

import numpy as np

SKILL_DEDUP_THRESHOLD = 0.82  # cosine similarity above which two skills are "the same"


def upsert_node(s: Session, node_type: str, *, natural_key: dict, defaults: dict | None = None):
    """Find a node by its natural key (the UniqueConstraint columns) or create it."""
    model = NODE_MODELS[node_type]
    stmt = select(model).filter_by(**natural_key)
    obj = s.scalars(stmt).first()
    if obj is None:
        obj = model(**natural_key, **(defaults or {}))
        s.add(obj)
        s.flush()  # assign obj.id now so callers can build edges
    return obj


def upsert_edge(s: Session, src_type, src_id, tgt_type, tgt_id, relation, weight: float = 1.0) -> None:
    exists = s.scalars(
        select(Edge).filter_by(
            source_type=src_type, source_id=src_id,
            target_type=tgt_type, target_id=tgt_id, relation=relation,
        )
    ).first()
    if exists is None:
        s.add(Edge(source_type=src_type, source_id=src_id, target_type=tgt_type,
                   target_id=tgt_id, relation=relation, weight=weight))


def get_or_create_skill(s: Session, name: str, category: str = "general", description: str = "") -> Skill:
    """Skills are the messiest nodes -- 'KYC checks', 'KYC verification',
    'Know Your Customer' are one skill. Exact-match first, then embedding
    similarity against existing skills before inserting a new one."""
    name = name.strip()
    exact = s.scalars(select(Skill).filter(Skill.name.ilike(name))).first()
    if exact:
        return exact

    existing = s.scalars(select(Skill)).all()
    if existing:
        query_vec = embed([name])[0]
        names = [sk.name for sk in existing]
        mat = embed(names)  # (n, dim), already normalised
        sims = mat @ query_vec
        best = int(np.argmax(sims))
        if sims[best] >= SKILL_DEDUP_THRESHOLD:
            return existing[best]

    skill = Skill(name=name, category=category, description=description)
    s.add(skill)
    s.flush()
    return skill

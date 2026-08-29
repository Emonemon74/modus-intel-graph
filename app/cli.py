"""Command-line entry point.

    uv run python -m app.cli init                 # create tables
    uv run python -m app.cli ingest "Retail Banking"
    uv run python -m app.cli stats
    uv run python -m app.cli reset                # wipe the graph (keeps schema)
"""

import sys

from sqlalchemy import delete, func, select

from app.db import Base, engine, init_db, session_scope
from app.models import (
    Activity, Edge, Industry, Process, Role, Skill, Source,
)


def cmd_init() -> None:
    init_db()
    print("schema ready")


def cmd_ingest(industry: str, from_step: str | None = None) -> None:
    from app.pipeline.ingest import run_ingest

    init_db()
    job_id = run_ingest(industry, from_step=from_step)
    print(f"\ningest complete (job {job_id})")
    cmd_stats()


def cmd_stats() -> None:
    with session_scope() as s:
        for label, model in [("industries", Industry), ("processes", Process),
                             ("activities", Activity), ("roles", Role),
                             ("skills", Skill), ("edges", Edge), ("sources", Source)]:
            print(f"  {label:12} {s.scalar(select(func.count()).select_from(model))}")
        print("  edges by relation:")
        for rel, n in s.execute(select(Edge.relation, func.count()).group_by(Edge.relation)):
            print(f"    {rel:26} {n}")


def cmd_reindex() -> None:
    """Rebuild the FAISS evidence index from the `sources` table."""
    from app.ai.embeddings import EvidenceIndex
    from app.models import Source

    idx = EvidenceIndex()
    idx.index.reset()
    idx.meta.clear()
    with session_scope() as s:
        items = [{"source_id": src.id, "text": src.raw_excerpt}
                 for src in s.scalars(select(Source)) if src.raw_excerpt]
    idx.add(items)
    idx.save()
    print(f"reindexed {len(items)} source snippets -> {idx.index.ntotal} vectors")


def cmd_export(path: str = "data/sample_graph.json") -> None:
    """Dump the whole graph + overlays to JSON -- the 'sample/synthetic data' deliverable."""
    import json

    from app.models import (
        Activity, AIOpportunity, Edge, Industry, Process, Role, Skill, SkillImpact, Stage,
    )

    def rows(model):
        with session_scope() as s:
            return [{c.name: getattr(o, c.name) for c in model.__table__.columns}
                    for o in s.scalars(select(model))]

    data = {name: rows(m) for name, m in [
        ("industries", Industry), ("stages", Stage), ("processes", Process),
        ("activities", Activity), ("roles", Role), ("skills", Skill),
        ("edges", Edge), ("ai_opportunities", AIOpportunity), ("skill_impacts", SkillImpact),
    ]}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"wrote {path}: " + ", ".join(f"{len(v)} {k}" for k, v in data.items()))


def cmd_reset() -> None:
    Base.metadata.drop_all(engine)
    init_db()
    print("graph wiped, schema recreated")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, *rest = args
    if cmd == "init":
        cmd_init()
    elif cmd == "ingest":
        industry = rest[0] if rest else "Retail Banking"
        from_step = rest[2] if len(rest) > 2 and rest[1] == "--from" else None
        cmd_ingest(industry, from_step)
    elif cmd == "reindex":
        cmd_reindex()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "export":
        cmd_export(rest[0] if rest else "data/sample_graph.json")
    elif cmd == "reset":
        cmd_reset()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

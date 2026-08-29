"""Command-line entry point.

    uv run python -m app.cli init                       # create tables
    uv run python -m app.cli ingest "Retail Banking"    # build the graph
    uv run python -m app.cli ingest "X" --from analyse  # resume from a step
    uv run python -m app.cli load-sample                # load data/sample_graph.json (no LLM key needed)
    uv run python -m app.cli export                     # dump graph+overlays+evidence -> sample_graph.json
    uv run python -m app.cli export-sources             # dump research sources + what they support
    uv run python -m app.cli reindex                    # rebuild FAISS from the sources table
    uv run python -m app.cli reclassify-skills          # re-run just the skill-impact step
    uv run python -m app.cli stats
    uv run python -m app.cli reset                      # wipe the graph (keeps schema)
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
        Activity, AIOpportunity, CascadeResult, CascadeRun, ClaimEvidence, Edge,
        Industry, Process, Role, Skill, SkillImpact, Source, Stage,
    )

    def rows(model):
        with session_scope() as s:
            return [{c.name: getattr(o, c.name) for c in model.__table__.columns}
                    for o in s.scalars(select(model))]

    data = {name: rows(m) for name, m in [
        ("industries", Industry), ("stages", Stage), ("processes", Process),
        ("activities", Activity), ("roles", Role), ("skills", Skill),
        ("edges", Edge), ("ai_opportunities", AIOpportunity), ("skill_impacts", SkillImpact),
        ("sources", Source), ("claim_evidence", ClaimEvidence),
        ("cascade_runs", CascadeRun), ("cascade_results", CascadeResult),
    ]}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"wrote {path}: " + ", ".join(f"{len(v)} {k}" for k, v in data.items()))


def cmd_export_sources(path: str = "data/research_sources.json") -> None:
    """Dump every research source, with which AI claims it supports -- the
    'research sources' deliverable and a traceability audit trail."""
    import json

    from app.models import (
        Activity, AIOpportunity, ClaimEvidence, Skill, SkillImpact, Source,
    )

    with session_scope() as s:
        out = []
        for src in s.scalars(select(Source).order_by(Source.id)):
            supports = []
            for ce in s.scalars(select(ClaimEvidence).filter_by(source_id=src.id)):
                label = None
                if ce.claim_type == "ai_opportunity":
                    opp = s.get(AIOpportunity, ce.claim_id)
                    if opp:
                        label = f"AI opportunity: {s.get(Activity, opp.activity_id).name}"
                elif ce.claim_type == "skill_impact":
                    si = s.get(SkillImpact, ce.claim_id)
                    if si:
                        label = f"Skill impact: {s.get(Skill, si.skill_id).name}"
                if label:
                    supports.append({"claim": label, "relevance": round(ce.relevance, 3),
                                     "quote": ce.quote[:300]})
            out.append({
                "id": src.id, "kind": src.kind, "title": src.title,
                "url": src.url, "publisher": src.publisher,
                "retrieved_at": src.retrieved_at.isoformat() if src.retrieved_at else None,
                "excerpt": src.raw_excerpt[:600],
                "supports_claims": supports,
            })
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    linked = sum(1 for x in out if x["supports_claims"])
    print(f"wrote {path}: {len(out)} sources ({linked} cited by >=1 AI claim)")


def cmd_reclassify_skills() -> None:
    """Re-run only step 9 (skill-impact classification) against the existing graph."""
    from app.models import SkillImpact
    from app.pipeline.ingest import run_ingest

    with session_scope() as s:
        s.execute(delete(SkillImpact))
        industry = s.scalars(select(Industry.name)).first()
    run_ingest(industry, from_step="classify")
    print("skill impacts recomputed")


def cmd_load_sample(path: str = "data/sample_graph.json") -> None:
    """Load a previously exported graph into a fresh DB. Lets a reviewer explore
    the full application (UI, graph navigation, evidence) with NO LLM key -- only
    the live cascade / add-entity features need a model."""
    import json
    from datetime import datetime

    from app.models import (
        Activity, AIOpportunity, CascadeResult, CascadeRun, ClaimEvidence, Edge,
        Industry, Process, Role, Skill, SkillImpact, Source, Stage,
    )

    models = {
        "industries": Industry, "stages": Stage, "processes": Process,
        "activities": Activity, "roles": Role, "skills": Skill, "edges": Edge,
        "ai_opportunities": AIOpportunity, "skill_impacts": SkillImpact,
        "sources": Source, "claim_evidence": ClaimEvidence,
        "cascade_runs": CascadeRun, "cascade_results": CascadeResult,
    }
    with open(path) as f:
        data = json.load(f)

    Base.metadata.drop_all(engine)
    init_db()
    with session_scope() as s:
        for key, model in models.items():
            for row in data.get(key, []):
                clean = {}
                for k, v in row.items():
                    if k.endswith("_at") and isinstance(v, str):
                        try:
                            v = datetime.fromisoformat(v)
                        except ValueError:
                            v = None
                    clean[k] = v
                s.add(model(**clean))
    print(f"loaded {path}: " + ", ".join(f"{len(data.get(k, []))} {k}" for k in models))
    if data.get("sources"):
        cmd_reindex()


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
    elif cmd == "export-sources":
        cmd_export_sources(rest[0] if rest else "data/research_sources.json")
    elif cmd == "reclassify-skills":
        cmd_reclassify_skills()
    elif cmd == "load-sample":
        cmd_load_sample(rest[0] if rest else "data/sample_graph.json")
    elif cmd == "reset":
        cmd_reset()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

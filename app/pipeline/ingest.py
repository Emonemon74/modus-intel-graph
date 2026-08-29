"""The ingest pipeline: an industry name in, a fully analysed graph out.

Nine steps. Each step reads its worklist in a short transaction, then processes
one item per transaction so a crash (or Ctrl-C, or a rate-limit giving up)
loses at most one item -- rerun `ingest` and it resumes where it stopped.
The same building blocks power the live "surprise record" test (add_entity.py).

    1 seed industry + value-chain stages
    2 stages   -> processes
    3 processes-> activities
    4 industry -> roles
    5 roles  x activities  -> ROLE_PERFORMS_ACTIVITY edges
    6 activities-> skills  -> ACTIVITY_REQUIRES_SKILL (+ ROLE_HAS_SKILL rollup)
    7 research every process & skill  -> Source rows + FAISS
    8 analyse every activity -> AIOpportunity (+ evidence)
    9 classify every skill   -> SkillImpact  (+ evidence)
"""

from sqlalchemy import select

from app.ai import analysts
from app.ai.embeddings import EvidenceIndex
from app.config import settings
from app.db import session_scope
from app.graph.store import get_or_create_skill, upsert_edge, upsert_node
from app.graph.traverse import neighbours
from app.models import (
    Activity, AIOpportunity, Industry, Job, Process, Role, Skill, SkillImpact, Stage,
)
from app.pipeline.evidence import attach_evidence
from app.pipeline.research import research_entity


def _set_step(job_id: int, step: str, detail: str = "") -> None:
    with session_scope() as s:
        job = s.get(Job, job_id)
        job.step, job.detail = step, detail
    print(f"  [{step}] {detail}", flush=True)


STEPS = [
    ("industry_stages", lambda *a: _step1_industry_stages(*a)),
    ("processes", lambda *a: _step2_processes(*a)),
    ("activities", lambda *a: _step3_activities(*a)),
    ("roles", lambda *a: _step4_roles(*a)),
    ("role_activity", lambda *a: _step5_role_activity(*a)),
    ("skills", lambda *a: _step6_skills(*a)),
    ("research", lambda *a: _step7_research(*a)),
    ("analyse", lambda *a: _step8_analyse_activities(*a)),
    ("classify", lambda *a: _step9_classify_skills(*a)),
]


def run_ingest(industry_name: str, from_step: str | None = None) -> int:
    """`from_step` (one of the STEPS names) resumes an interrupted ingest,
    skipping earlier steps. Steps 8/9 are item-level resumable regardless."""
    index = EvidenceIndex()
    with session_scope() as s:
        job = Job(kind="ingest", target=industry_name, status="running")
        s.add(job)
        s.flush()
        job_id = job.id

    names = [n for n, _ in STEPS]
    start = names.index(from_step) if from_step in names else 0
    try:
        for name, fn in STEPS[start:]:
            fn(job_id, industry_name, index)
        index.save()
        with session_scope() as s:
            s.get(Job, job_id).status = "done"
        return job_id
    except Exception as e:
        index.save()
        with session_scope() as s:
            j = s.get(Job, job_id)
            j.status, j.detail = "error", f"{j.step}: {e}"
        raise


def _industry(s, name):
    return s.scalars(select(Industry).filter_by(name=name)).one()


# --------------------------------------------------------------------------- #
def _step1_industry_stages(job_id, industry_name, index):
    _set_step(job_id, "industry_stages", industry_name)
    data = analysts.extract_stages(industry_name)
    with session_scope() as s:
        ind = upsert_node(s, "industry", natural_key={"name": industry_name})
        for i, st in enumerate(data.stages):
            upsert_node(s, "stage",
                        natural_key={"industry_id": ind.id, "name": st.name},
                        defaults={"sequence": i, "description": st.description})


def _step2_processes(job_id, industry_name, index):
    with session_scope() as s:
        ind = _industry(s, industry_name)
        stages = [(st.id, st.name, st.description)
                  for st in s.scalars(select(Stage).filter_by(industry_id=ind.id))]
    for stage_id, name, desc in stages:
        _set_step(job_id, "processes", name)
        data = analysts.extract_processes(industry_name, name, desc)
        with session_scope() as s:
            for p in data.processes[: settings.max_processes_per_stage]:
                proc = upsert_node(s, "process",
                                   natural_key={"stage_id": stage_id, "name": p.name},
                                   defaults={"purpose": p.purpose})
                upsert_edge(s, "stage", stage_id, "process", proc.id, "STAGE_HAS_PROCESS")


def _step3_activities(job_id, industry_name, index):
    with session_scope() as s:
        procs = [(p.id, p.name, p.purpose) for p in s.scalars(select(Process))]
    for proc_id, name, purpose in procs:
        _set_step(job_id, "activities", name)
        data = analysts.extract_activities(industry_name, name, purpose)
        with session_scope() as s:
            for a in data.activities[: settings.max_activities_per_process]:
                act = upsert_node(s, "activity",
                                  natural_key={"process_id": proc_id, "name": a.name},
                                  defaults={"description": a.description,
                                            "automation_potential": (a.automation_potential.upper()[:1] or "M")})
                upsert_edge(s, "process", proc_id, "activity", act.id, "PROCESS_HAS_ACTIVITY")


def _step4_roles(job_id, industry_name, index):
    _set_step(job_id, "roles", industry_name)
    data = analysts.extract_roles(industry_name)
    with session_scope() as s:
        ind = _industry(s, industry_name)
        for r in data.roles[: settings.max_roles]:
            upsert_node(s, "role",
                        natural_key={"industry_id": ind.id, "name": r.name},
                        defaults={"description": r.description, "seniority": r.seniority})


def _step5_role_activity(job_id, industry_name, index):
    _set_step(job_id, "role_activity", "linking roles to activities")
    with session_scope() as s:
        ind = _industry(s, industry_name)
        roles = {r.name: r.id for r in s.scalars(select(Role).filter_by(industry_id=ind.id))}
        acts = {a.name: a.id for a in s.scalars(select(Activity))}
    if not roles or not acts:
        return
    mapping = analysts.map_roles_to_activities(industry_name, list(roles), list(acts))
    with session_scope() as s:
        for link in mapping.links:
            rid = roles.get(link.role)
            if not rid:
                continue
            for act_name in link.activities:
                aid = acts.get(act_name)
                if aid:
                    upsert_edge(s, "role", rid, "activity", aid, "ROLE_PERFORMS_ACTIVITY")


def _step6_skills(job_id, industry_name, index):
    with session_scope() as s:
        acts = [(a.id, a.name, a.description) for a in s.scalars(select(Activity))]
    for act_id, name, desc in acts:
        _set_step(job_id, "skills", name)
        data = analysts.extract_skills(industry_name, name, desc)
        with session_scope() as s:
            for sk in data.skills[: settings.max_skills_per_activity]:
                skill = get_or_create_skill(s, sk.name, sk.category)
                upsert_edge(s, "activity", act_id, "skill", skill.id, "ACTIVITY_REQUIRES_SKILL")
    # ROLE_HAS_SKILL rollup: a role has every skill required by activities it performs
    _set_step(job_id, "skills", "role->skill rollup")
    with session_scope() as s:
        for role in s.scalars(select(Role)):
            skill_ids = set()
            for _r, _d, _nt, aid, _e in neighbours(s, "role", role.id, ["ROLE_PERFORMS_ACTIVITY"]):
                for _r2, _d2, _nt2, sid, _e2 in neighbours(s, "activity", aid, ["ACTIVITY_REQUIRES_SKILL"]):
                    skill_ids.add(sid)
            for sid in skill_ids:
                upsert_edge(s, "role", role.id, "skill", sid, "ROLE_HAS_SKILL")


def _step7_research(job_id, industry_name, index):
    # Research every process, but only the most-connected skills -- a web search
    # per skill does not scale and low-degree skills add little evidence value.
    with session_scope() as s:
        targets = [("process", p.name) for p in s.scalars(select(Process))]
        skill_degree: dict[str, int] = {}
        for sk in s.scalars(select(Skill)):
            deg = len(neighbours(s, "skill", sk.id, ["ACTIVITY_REQUIRES_SKILL"]))
            skill_degree[sk.name] = deg
        top_skills = sorted(skill_degree, key=skill_degree.get, reverse=True)[: settings.max_research_skills]
        targets += [("skill", name) for name in top_skills]
    for kind, name in targets:
        _set_step(job_id, "research", f"{kind}: {name}")
        with session_scope() as s:
            research_entity(s, name, index)
    index.save()


def _step8_analyse_activities(job_id, industry_name, index):
    with session_scope() as s:
        todo = [(a.id, a.name, a.description) for a in s.scalars(select(Activity))
                if not s.scalars(select(AIOpportunity).filter_by(activity_id=a.id)).first()]
    for act_id, name, desc in todo:
        _set_step(job_id, "analyse_activity", name)
        with session_scope() as s:
            ev = attach_evidence(s, index, "activity_pre", act_id,
                                 f"{name} {desc} AI automation", k=3)
            out = analysts.analyse_activity(industry_name, name, desc, ev)
            opp = AIOpportunity(
                activity_id=act_id, summary=out.summary, ai_capability=out.ai_capability,
                benefit=out.benefit, risk=out.risk,
                automation_type=out.automation_type.upper(), confidence=out.confidence,
                rationale=out.rationale,
            )
            s.add(opp)
            s.flush()
            attach_evidence(s, index, "ai_opportunity", opp.id, f"{name} {out.summary}", k=3)


def _step9_classify_skills(job_id, industry_name, index):
    with session_scope() as s:
        todo = [(sk.id, sk.name) for sk in s.scalars(select(Skill))
                if not s.scalars(select(SkillImpact).filter_by(skill_id=sk.id)).first()]
    for skill_id, name in todo:
        _set_step(job_id, "classify_skill", name)
        with session_scope() as s:
            act_ctx = ", ".join(
                s.get(Activity, aid).name
                for _r, _d, _nt, aid, _e in neighbours(s, "skill", skill_id, ["ACTIVITY_REQUIRES_SKILL"])
            )[:400]
            ev = attach_evidence(s, index, "skill_pre", skill_id,
                                 f"{name} future of work AI impact", k=3)
            out = analysts.classify_skill(industry_name, name, ev, act_ctx)
            si = SkillImpact(skill_id=skill_id, classification=out.classification.upper(),
                             rationale=out.rationale, confidence=out.confidence)
            s.add(si)
            s.flush()
            attach_evidence(s, index, "skill_impact", si.id, f"{name} {out.rationale}", k=3)

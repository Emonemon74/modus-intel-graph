"""The "surprise record" test.

A judge names a process / role / skill that is not in the graph. We insert it and
run only the pipeline steps relevant to that node type, reusing the same analyst
functions as the bulk ingest. Tuned to return in ~30-60s: tighter fan-out caps,
one batched role-mapping call, research off by default, and each stage committed
as it completes so partial progress is never lost.
"""

from sqlalchemy import select

from app.ai import analysts
from app.ai.embeddings import EvidenceIndex
from app.config import settings
from app.db import session_scope
from app.graph.store import get_or_create_skill, upsert_edge, upsert_node
from app.graph.traverse import neighbours
from app.models import Activity, AIOpportunity, Industry, Role, SkillImpact, Stage
from app.pipeline.evidence import attach_evidence
from app.pipeline.research import research_entity


def _industry_id(s) -> tuple[int, str]:
    ind = s.scalars(select(Industry)).first()
    if not ind:
        raise ValueError("ingest an industry first")
    return ind.id, ind.name


def add_process(name: str, context: str = "") -> dict:
    index = EvidenceIndex()

    # 1) create the process + its activities (one short txn)
    with session_scope() as s:
        ind_id, ind_name = _industry_id(s)
        stage = s.scalars(select(Stage).filter_by(industry_id=ind_id)).first() \
            or upsert_node(s, "stage", natural_key={"industry_id": ind_id, "name": "Other"})
        proc = upsert_node(s, "process",
                           natural_key={"stage_id": stage.id, "name": name},
                           defaults={"purpose": context})
        upsert_edge(s, "stage", stage.id, "process", proc.id, "STAGE_HAS_PROCESS")
        proc_id = proc.id

    acts = analysts.extract_activities(ind_name, name, context or name)
    activity_ids: list[int] = []
    with session_scope() as s:
        for a in acts.activities[: settings.live_max_activities]:
            act = upsert_node(s, "activity",
                              natural_key={"process_id": proc_id, "name": a.name},
                              defaults={"description": a.description,
                                        "automation_potential": (a.automation_potential.upper()[:1] or "M")})
            upsert_edge(s, "process", proc_id, "activity", act.id, "PROCESS_HAS_ACTIVITY")
            activity_ids.append(act.id)

    created = {"process": proc_id, "activities": activity_ids, "skills": []}

    # 2) per activity: skills + AI opportunity (one txn each)
    for act_id in activity_ids:
        with session_scope() as s:
            act = s.get(Activity, act_id)
            skills = analysts.extract_skills(ind_name, act.name, act.description)
            for sk in skills.skills[: settings.live_max_skills_per_activity]:
                skill = get_or_create_skill(s, sk.name, sk.category)
                upsert_edge(s, "activity", act_id, "skill", skill.id, "ACTIVITY_REQUIRES_SKILL")
                created["skills"].append(skill.id)

            ev = ""
            if settings.live_research:
                research_entity(s, act.name, index)
                ev = attach_evidence(s, index, "activity_pre", act_id,
                                     f"{act.name} AI automation", k=3)
            out = analysts.analyse_activity(ind_name, act.name, act.description, ev)
            opp = AIOpportunity(activity_id=act_id, summary=out.summary,
                                ai_capability=out.ai_capability, benefit=out.benefit,
                                risk=out.risk, automation_type=out.automation_type.upper(),
                                confidence=out.confidence, rationale=out.rationale)
            s.add(opp)
            s.flush()
            attach_evidence(s, index, "ai_opportunity", opp.id, f"{act.name} {out.summary}", k=3)

    # 3) one batched call: which existing roles perform the new activities
    with session_scope() as s:
        roles = {r.name: r.id for r in s.scalars(select(Role).filter_by(industry_id=ind_id))}
        act_names = {s.get(Activity, i).name: i for i in activity_ids}
    if roles and act_names:
        m = analysts.map_roles_to_activities(ind_name, list(roles), list(act_names))
        with session_scope() as s:
            for link in m.links:
                rid = roles.get(link.role)
                if not rid:
                    continue
                for an in link.activities:
                    aid = act_names.get(an)
                    if aid:
                        upsert_edge(s, "role", rid, "activity", aid, "ROLE_PERFORMS_ACTIVITY")
                        for _r, _d, _nt, sid, _e in neighbours(s, "activity", aid, ["ACTIVITY_REQUIRES_SKILL"]):
                            upsert_edge(s, "role", rid, "skill", sid, "ROLE_HAS_SKILL")

    # 4) classify any brand-new skills (capped)
    for sid in list(dict.fromkeys(created["skills"]))[:6]:
        with session_scope() as s:
            if s.scalars(select(SkillImpact).filter_by(skill_id=sid)).first():
                continue
            from app.models import Skill
            sk = s.get(Skill, sid)
            out = analysts.classify_skill(ind_name, sk.name, "", name)
            s.add(SkillImpact(skill_id=sid, classification=out.classification.upper(),
                              rationale=out.rationale, confidence=out.confidence))

    index.save()
    return created


def add_role(name: str, context: str = "") -> dict:
    with session_scope() as s:
        ind_id, ind_name = _industry_id(s)
        role = upsert_node(s, "role",
                           natural_key={"industry_id": ind_id, "name": name},
                           defaults={"description": context})
        role_id = role.id
        activities = {a.name: a.id for a in s.scalars(select(Activity))}

    if activities:
        m = analysts.map_roles_to_activities(ind_name, [name], list(activities))
        with session_scope() as s:
            for link in m.links:
                if link.role != name:
                    continue
                for an in link.activities:
                    aid = activities.get(an)
                    if aid:
                        upsert_edge(s, "role", role_id, "activity", aid, "ROLE_PERFORMS_ACTIVITY")
            for _r, _d, _nt, aid, _e in neighbours(s, "role", role_id, ["ROLE_PERFORMS_ACTIVITY"]):
                for _r2, _d2, _nt2, sid, _e2 in neighbours(s, "activity", aid, ["ACTIVITY_REQUIRES_SKILL"]):
                    upsert_edge(s, "role", role_id, "skill", sid, "ROLE_HAS_SKILL")
    return {"role": role_id}


def add_skill(name: str, context: str = "") -> dict:
    index = EvidenceIndex()
    with session_scope() as s:
        ind_id, ind_name = _industry_id(s)
        skill = get_or_create_skill(s, name, "general", context)
        skill_id = skill.id

    ev = ""
    if settings.live_research:
        with session_scope() as s:
            research_entity(s, name, index)
            ev = attach_evidence(s, index, "skill_pre", skill_id,
                                 f"{name} future skill AI impact", k=3)
    out = analysts.classify_skill(ind_name, name, ev, context or "general")
    with session_scope() as s:
        existing = s.scalars(select(SkillImpact).filter_by(skill_id=skill_id)).first()
        if existing:
            existing.classification = out.classification.upper()
            existing.rationale = out.rationale
        else:
            s.add(SkillImpact(skill_id=skill_id, classification=out.classification.upper(),
                              rationale=out.rationale, confidence=out.confidence))
    index.save()
    return {"skill": skill_id}


DISPATCH = {"process": add_process, "role": add_role, "skill": add_skill}

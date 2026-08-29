"""Graph-derived overlays -- computed by traversing the stored graph, with no
LLM call. This is the 'Future Change' overlay for roles and processes that
Assignment 11 asks for across the whole graph, and it answers the example
navigation queries ("select a process -> see affected roles") directly.

Because it is pure aggregation over persisted edges + the activity / skill
overlays, it scales with the graph and is fully traceable: every number here
can be checked against the rows it counts.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.traverse import get_node, neighbours, node_label
from app.models import AIOpportunity, SkillImpact

_AUTO_WEIGHT = {"AUTOMATE": 1.0, "AUGMENT": 0.5, "UNCHANGED": 0.0}
_SKILL_PRESSURE = {  # how much AI is expected to change demand for the skill
    "DECLINING": 1.0, "CHANGING": 0.7, "AI_AUGMENTED": 0.5,
    "EMERGING": 0.4, "INCREASING": 0.3, "ENDURING_HUMAN": 0.1,
}


def _activity_ids_for_role(s: Session, role_id: int) -> list[int]:
    return [ni for _r, _d, _nt, ni, _e in
            neighbours(s, "role", role_id, ["ROLE_PERFORMS_ACTIVITY"])]


def role_impact(s: Session, role_id: int) -> dict:
    """Future-change profile for a role, aggregated from its activities + skills."""
    act_ids = _activity_ids_for_role(s, role_id)
    auto_counts = {"AUTOMATE": 0, "AUGMENT": 0, "UNCHANGED": 0, "unassessed": 0}
    exposure_num = 0.0
    for aid in act_ids:
        opp = s.scalars(select(AIOpportunity).where(AIOpportunity.activity_id == aid)).first()
        atype = opp.automation_type if opp else None
        if atype in auto_counts:
            auto_counts[atype] += 1
            exposure_num += _AUTO_WEIGHT[atype]
        else:
            auto_counts["unassessed"] += 1
    exposure = round(exposure_num / len(act_ids), 2) if act_ids else 0.0

    skill_ids = {ni for _r, _d, _nt, ni, _e in
                 neighbours(s, "role", role_id, ["ROLE_HAS_SKILL"])}
    skill_classes: dict[str, int] = {}
    pressure_num = 0.0
    for sid in skill_ids:
        si = s.scalars(select(SkillImpact).where(SkillImpact.skill_id == sid)).first()
        cls = si.classification if si else "unassessed"
        skill_classes[cls] = skill_classes.get(cls, 0) + 1
        pressure_num += _SKILL_PRESSURE.get(cls, 0.3)
    skill_pressure = round(pressure_num / len(skill_ids), 2) if skill_ids else 0.0

    band = ("High" if exposure >= 0.6 else "Moderate" if exposure >= 0.35 else "Low")
    headline = (
        f"{band} AI exposure. Of {len(act_ids)} activities, "
        f"{auto_counts['AUTOMATE']} are automatable and {auto_counts['AUGMENT']} AI-augmented; "
        f"{skill_classes.get('DECLINING', 0)} of {len(skill_ids)} skills are declining, "
        f"{skill_classes.get('EMERGING', 0)} emerging."
    )
    return {
        "role_impact": {
            "ai_exposure": exposure,             # 0-1, activity-weighted
            "skill_pressure": skill_pressure,    # 0-1, skill-demand-shift weighted
            "exposure_band": band,
            "activities_total": len(act_ids),
            "activity_breakdown": auto_counts,
            "skills_total": len(skill_ids),
            "skill_breakdown": skill_classes,
            "headline": headline,
            "derived_from": "counts over ROLE_PERFORMS_ACTIVITY + ai_opportunities and "
                            "ROLE_HAS_SKILL + skill_impacts",
        }
    }


def process_roles(s: Session, process_id: int) -> dict:
    """Roles affected by a process = union of roles performing its activities."""
    act_ids = [ni for _r, _d, _nt, ni, _e in
               neighbours(s, "process", process_id, ["PROCESS_HAS_ACTIVITY"])]
    role_ids: set[int] = set()
    for aid in act_ids:
        for _r, _d, _nt, ni, _e in neighbours(s, "activity", aid, ["ROLE_PERFORMS_ACTIVITY"]):
            role_ids.add(ni)
    roles = []
    for rid in role_ids:
        r = get_node(s, "role", rid)
        if r:
            roles.append({"id": rid, "label": node_label(r)})
    return {"affected_roles": sorted(roles, key=lambda x: x["label"])}


def process_impact(s: Session, process_id: int) -> dict:
    """AI-opportunity roll-up for a process from its activities."""
    act_ids = [ni for _r, _d, _nt, ni, _e in
               neighbours(s, "process", process_id, ["PROCESS_HAS_ACTIVITY"])]
    counts = {"AUTOMATE": 0, "AUGMENT": 0, "UNCHANGED": 0, "unassessed": 0}
    for aid in act_ids:
        opp = s.scalars(select(AIOpportunity).where(AIOpportunity.activity_id == aid)).first()
        counts[opp.automation_type if opp and opp.automation_type in counts else "unassessed"] += 1
    n = max(len(act_ids), 1)
    score = round((counts["AUTOMATE"] + 0.5 * counts["AUGMENT"]) / n, 2)
    return {"process_impact": {"activities_total": len(act_ids),
                               "activity_breakdown": counts,
                               "ai_opportunity_score": score,
                               "derived_from": "counts over PROCESS_HAS_ACTIVITY + ai_opportunities"}}

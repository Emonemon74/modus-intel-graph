"""One function per reasoning step. Each wraps `complete_json` with a focused
prompt. The pipeline calls these; they never touch the database.

Every prompt says "base this on the EVIDENCE below" so outputs stay grounded in
the retrieved Source snippets rather than the model's free association.
"""

from app.ai.llm import complete_json
from app.ai import schemas as S
from app.config import settings

SYS = "You are an enterprise transformation analyst. Be concrete, industry-specific, and terse."


def extract_stages(industry: str) -> S.StageList:
    return complete_json(
        "extract_stages", SYS,
        f"List the major value-chain stages of the {industry} industry, in order "
        f"(max 7). A stage is a broad phase of how the industry creates value.",
        S.StageList,
    )


def extract_processes(industry: str, stage: str, stage_desc: str) -> S.ProcessList:
    return complete_json(
        "extract_processes", SYS,
        f"Industry: {industry}\nValue-chain stage: {stage} -- {stage_desc}\n"
        f"List up to {settings.max_processes_per_stage} concrete business processes "
        f"that live in this stage. Give each a one-line purpose.",
        S.ProcessList,
    )


def extract_activities(industry: str, process: str, purpose: str) -> S.ActivityList:
    return complete_json(
        "extract_activities", SYS,
        f"Industry: {industry}\nProcess: {process} -- {purpose}\n"
        f"Break this process into up to {settings.max_activities_per_process} discrete "
        f"activities (the actual steps people perform). For each, rate automation "
        f"potential as L, M, or H.",
        S.ActivityList,
    )


def extract_roles(industry: str) -> S.RoleList:
    return complete_json(
        "extract_roles", SYS,
        f"List up to {settings.max_roles} representative operational and management "
        f"roles in the {industry} industry (job titles). Include a short description "
        f"and seniority (junior/mid/senior/exec) for each.",
        S.RoleList,
    )


def map_roles_to_activities(industry: str, roles: list[str], activities: list[str]) -> S.RoleActivityMap:
    return complete_json(
        "map_roles_activities", SYS,
        f"Industry: {industry}\nRoles:\n- " + "\n- ".join(roles)
        + "\n\nActivities:\n- " + "\n- ".join(activities)
        + "\n\nFor each role, list which of the above activities it typically performs. "
          "Only use activity names from the list. Omit roles that perform none.",
        S.RoleActivityMap,
    )


def extract_skills(industry: str, activity: str, description: str) -> S.SkillList:
    return complete_json(
        "extract_skills", SYS,
        f"Industry: {industry}\nActivity: {activity} -- {description}\n"
        f"List up to {settings.max_skills_per_activity} specific skills a person needs "
        f"to perform this activity well. Use canonical skill names. Category one of: "
        f"technical, analytical, interpersonal, domain, compliance, general.",
        S.SkillList,
    )


def analyse_activity(industry: str, activity: str, description: str, evidence: str) -> S.AIOpportunityOut:
    return complete_json(
        "analyse_activity", SYS,
        f"Industry: {industry}\nActivity: {activity} -- {description}\n\n"
        f"EVIDENCE:\n{evidence or '(no external evidence found; reason from domain knowledge)'}\n\n"
        f"Assess the AI opportunity for this activity: what AI capability applies, the "
        f"benefit, the risk, and whether AI would AUTOMATE it, AUGMENT the human, or "
        f"leave it UNCHANGED. Give confidence 0-1 and a one-line rationale citing the evidence.",
        S.AIOpportunityOut,
    )


def classify_skill(industry: str, skill: str, evidence: str, activity_context: str) -> S.SkillImpactOut:
    return complete_json(
        "classify_skill", SYS,
        f"Industry: {industry}\nSkill: {skill}\nUsed in activities: {activity_context}\n\n"
        f"EVIDENCE:\n{evidence or '(none; reason from domain knowledge)'}\n\n"
        f"Classify how AI/automation will change demand for this skill: EMERGING, "
        f"INCREASING, AI_AUGMENTED, CHANGING, DECLINING, or ENDURING_HUMAN. "
        f"Give a one-line rationale and confidence 0-1.",
        S.SkillImpactOut,
    )


def cascade_effect(hypothesis: str, from_label: str, to_type: str, to_label: str, evidence: str) -> S.CascadeEffectOut:
    return complete_json(
        "cascade_effect", SYS,
        f"Hypothesis: {hypothesis}\n"
        f"This change originates at: {from_label}\n"
        f"Question: is the {to_type} '{to_label}' meaningfully affected as a knock-on consequence?\n\n"
        f"EVIDENCE:\n{evidence or '(none)'}\n\n"
        f"Answer material=true only if there is a real downstream impact. If true, "
        f"describe the effect on '{to_label}' in one sentence and give brief reasoning.",
        S.CascadeEffectOut,
    )

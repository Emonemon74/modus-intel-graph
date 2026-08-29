"""Pydantic schemas for every structured LLM output.

These double as (a) the JSON contract we hand the model and (b) validated Python
objects the pipeline consumes. If the model drifts, validation fails and we retry.
"""

from pydantic import BaseModel, Field


class StageOut(BaseModel):
    name: str
    description: str = ""


class StageList(BaseModel):
    stages: list[StageOut]


class ProcessOut(BaseModel):
    name: str
    purpose: str = ""


class ProcessList(BaseModel):
    processes: list[ProcessOut]


class ActivityOut(BaseModel):
    name: str
    description: str = ""
    automation_potential: str = Field("M", description="one of L, M, H")


class ActivityList(BaseModel):
    activities: list[ActivityOut]


class RoleOut(BaseModel):
    name: str
    description: str = ""
    seniority: str = "mid"


class RoleList(BaseModel):
    roles: list[RoleOut]


class RoleActivityLink(BaseModel):
    role: str
    activities: list[str]


class RoleActivityMap(BaseModel):
    links: list[RoleActivityLink]


class SkillOut(BaseModel):
    name: str
    category: str = "general"


class SkillList(BaseModel):
    skills: list[SkillOut]


class AIOpportunityOut(BaseModel):
    summary: str
    ai_capability: str = ""
    benefit: str = ""
    risk: str = ""
    automation_type: str = Field("AUGMENT", description="AUTOMATE, AUGMENT, or UNCHANGED")
    confidence: float = 0.5
    rationale: str = ""


class SkillImpactOut(BaseModel):
    classification: str = Field(
        ..., description="one of EMERGING, INCREASING, AI_AUGMENTED, CHANGING, DECLINING, ENDURING_HUMAN"
    )
    rationale: str = ""
    confidence: float = 0.5


class CascadeEffectOut(BaseModel):
    material: bool = Field(..., description="true only if this node is meaningfully affected")
    effect: str = ""
    reasoning: str = ""

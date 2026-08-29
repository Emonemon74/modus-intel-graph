"""The data model -- this IS the graph.

Design choice: concrete tables for each node kind (they have different
attributes), plus ONE generic `edges` table for every relationship. That single
typed edge table is what makes graph traversal uniform: "give me the neighbours
of node X" is one query regardless of node kind. Scaling from 25 processes to
2500 adds rows here, not code.

Node kinds: industry, stage, process, activity, role, skill
Relations: STAGE_HAS_PROCESS, PROCESS_HAS_ACTIVITY, ROLE_PERFORMS_ACTIVITY,
           ACTIVITY_REQUIRES_SKILL, ROLE_HAS_SKILL
"""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# --------------------------------------------------------------------------- #
# NODES                                                                       #
# --------------------------------------------------------------------------- #
class Industry(Base, TimestampMixin):
    __tablename__ = "industries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Stage(Base, TimestampMixin):
    """A value-chain stage, e.g. 'Customer Onboarding'."""

    __tablename__ = "stages"
    id: Mapped[int] = mapped_column(primary_key=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industries.id"))
    name: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("industry_id", "name"),)


class Process(Base, TimestampMixin):
    __tablename__ = "processes"
    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("stage_id", "name"),)


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    automation_potential: Mapped[str] = mapped_column(String(10), default="M")  # L / M / H
    __table_args__ = (UniqueConstraint("process_id", "name"),)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industries.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    seniority: Mapped[str] = mapped_column(String(30), default="mid")
    __table_args__ = (UniqueConstraint("industry_id", "name"),)


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[str] = mapped_column(Text, default="")


NODE_MODELS = {
    "industry": Industry,
    "stage": Stage,
    "process": Process,
    "activity": Activity,
    "role": Role,
    "skill": Skill,
}


# --------------------------------------------------------------------------- #
# EDGES -- one table for every relationship                                   #
# --------------------------------------------------------------------------- #
class Edge(Base, TimestampMixin):
    __tablename__ = "edges"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[int] = mapped_column(Integer)
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    relation: Mapped[str] = mapped_column(String(40))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "target_type", "target_id", "relation"),
        Index("ix_edge_source", "source_type", "source_id"),
        Index("ix_edge_target", "target_type", "target_id"),
        Index("ix_edge_relation", "relation"),
    )


# --------------------------------------------------------------------------- #
# OVERLAYS -- the "AI intelligence" layered on top of the structural graph    #
# --------------------------------------------------------------------------- #
class AIOpportunity(Base, TimestampMixin):
    __tablename__ = "ai_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    ai_capability: Mapped[str] = mapped_column(String(200), default="")
    benefit: Mapped[str] = mapped_column(Text, default="")
    risk: Mapped[str] = mapped_column(Text, default="")
    automation_type: Mapped[str] = mapped_column(String(20), default="AUGMENT")  # AUTOMATE/AUGMENT/UNCHANGED
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    rationale: Mapped[str] = mapped_column(Text, default="")


class SkillImpact(Base, TimestampMixin):
    __tablename__ = "skill_impacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), unique=True)
    # EMERGING / INCREASING / AI_AUGMENTED / CHANGING / DECLINING / ENDURING_HUMAN
    classification: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


class CascadeRun(Base, TimestampMixin):
    __tablename__ = "cascade_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_type: Mapped[str] = mapped_column(String(20))
    trigger_id: Mapped[int] = mapped_column(Integer)
    hypothesis: Mapped[str] = mapped_column(Text)
    results: Mapped[list["CascadeResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CascadeResult(Base):
    __tablename__ = "cascade_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cascade_runs.id"))
    affected_type: Mapped[str] = mapped_column(String(20))
    affected_id: Mapped[int] = mapped_column(Integer)
    depth: Mapped[int] = mapped_column(Integer, default=1)
    effect: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    path_json: Mapped[str] = mapped_column(Text, default="[]")
    run: Mapped[CascadeRun] = relationship(back_populates="results")


# --------------------------------------------------------------------------- #
# EVIDENCE & TRACEABILITY -- required: every AI claim must be traceable       #
# --------------------------------------------------------------------------- #
class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    publisher: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[str] = mapped_column(String(20), default="web")  # web / corpus / synthetic
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    raw_excerpt: Mapped[str] = mapped_column(Text, default="")


class ClaimEvidence(Base, TimestampMixin):
    """Links any AI-generated row to the Source(s) that back it."""

    __tablename__ = "claim_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_type: Mapped[str] = mapped_column(String(40))  # ai_opportunity / skill_impact / cascade_result / activity
    claim_id: Mapped[int] = mapped_column(Integer)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    quote: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    __table_args__ = (Index("ix_claim", "claim_type", "claim_id"),)


# --------------------------------------------------------------------------- #
# OPERATIONAL -- proves the pipeline is real & resumable, not hand-filled     #
# --------------------------------------------------------------------------- #
class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))       # ingest / add_entity / cascade
    target: Mapped[str] = mapped_column(String(200), default="")
    step: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/done/error
    detail: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class LLMCall(Base):
    """Every model call logged: prompt, response, tokens. Answers 'explain every
    component' and lets a reviewer audit exactly what the AI was asked."""

    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    purpose: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

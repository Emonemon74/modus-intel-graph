# Data model

SQLAlchemy models in `app/models.py`. SQLite by default; Postgres by changing
`DATABASE_URL`.

## Nodes (one table per kind — kinds carry different attributes)

| Table | Key columns | Natural key |
|---|---|---|
| `industries` | name, description | name |
| `stages` | industry_id, name, sequence, description | (industry_id, name) |
| `processes` | stage_id, name, purpose, description | (stage_id, name) |
| `activities` | process_id, name, description, **automation_potential** (L/M/H) | (process_id, name) |
| `roles` | industry_id, name, description, seniority | (industry_id, name) |
| `skills` | name, category, description | name (+ embedding-similarity dedup) |

## Edges — ONE typed table for every relationship

`edges(source_type, source_id, target_type, target_id, relation, weight)`

Indexed on `(source_type, source_id)`, `(target_type, target_id)`, `relation`.
Unique on the whole tuple (idempotent writes).

| relation | from → to |
|---|---|
| `STAGE_HAS_PROCESS` | stage → process |
| `PROCESS_HAS_ACTIVITY` | process → activity |
| `ROLE_PERFORMS_ACTIVITY` | role → activity |
| `ACTIVITY_REQUIRES_SKILL` | activity → skill |
| `ROLE_HAS_SKILL` | role → skill (rolled up via activities) |

Why one table: neighbour lookup is a single query for any node kind, so graph
traversal, the cascade reasoner, and the UI all share one code path — and adding
processes never means new tables.

## Overlays (AI-generated intelligence)

| Table | Per | Fields |
|---|---|---|
| `ai_opportunities` | activity | summary, ai_capability, benefit, risk, **automation_type** (AUTOMATE/AUGMENT/UNCHANGED), confidence, rationale |
| `skill_impacts` | skill | **classification** (EMERGING / INCREASING / AI_AUGMENTED / CHANGING / DECLINING / ENDURING_HUMAN), rationale, confidence |
| `cascade_runs` | query | trigger_type, trigger_id, hypothesis |
| `cascade_results` | affected node | affected_type/id, depth, effect, reasoning, path_json |

## Derived overlays (no table — computed on read)

`app/graph/rollup.py` aggregates the stored graph on each request, with **no LLM
call**, so every number is checkable against the rows it counts:

| For | Computation |
|---|---|
| **role** `role_impact` | AI-exposure (activity-weighted over `ai_opportunities`), skill-pressure (weighted over `skill_impacts`), activity + skill breakdowns, exposure band, headline |
| **process** `process_impact` | AI-opportunity score + activity breakdown from the process's activities |
| **process** `affected_roles` | union of roles performing the process's activities |

## Evidence & traceability

| Table | Fields |
|---|---|
| `sources` | url, title, publisher, kind (web/corpus/synthetic), retrieved_at, raw_excerpt |
| `claim_evidence` | claim_type, claim_id, source_id, quote, relevance (cosine score) |

`claim_type` + `claim_id` point at any overlay row (or `activity_pre` / `skill_pre`
for the evidence retrieved *before* an analysis). Every AI claim in the UI has a
"Show evidence" button that reads this.

## Operational

| Table | Purpose |
|---|---|
| `jobs` | one row per ingest / add / cascade run — step, status, detail. Makes ingest resumable. |
| `llm_calls` | every model call: purpose tag, model, full system+user prompt, response, token counts, latency. Stored in its own SQLite file (`data/llm_log.db`) so logging never contends with a pipeline transaction. |

## Entity-relationship sketch

```
industry ─< stage ─< process ─< activity >─ (edges) ─< skill
                                   │                      │
                              ai_opportunity         skill_impact
                                   │                      │
   role >──(edges: PERFORMS)───────┘                      │
    └────(edges: HAS_SKILL, via activities)───────────────┘

any overlay row ─< claim_evidence >─ source
cascade_run ─< cascade_result
```

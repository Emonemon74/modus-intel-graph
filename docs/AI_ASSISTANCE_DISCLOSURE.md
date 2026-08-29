# AI coding-tool disclosure

The challenge rules require disclosing where AI coding tools were used and
explaining what was personally designed and implemented.

## Tools used

- **Claude Code** (Anthropic) was used as an AI pair-programmer throughout:
  scaffolding, writing modules, debugging, and drafting documentation.
- The running application also calls an LLM at runtime (that is the point of the
  assignment) — see `docs/MODEL_AND_LIBRARY_INVENTORY.md`.

## Division of work

**Directed by the candidate:**
- Choice of assignment (11 — Process × Role × Skill graph) and industry (Retail Banking).
- The core modelling decision: concrete node tables + one generic typed `edges`
  table, so traversal and the cascade share a single code path and scale by rows.
- Scope and pacing decisions during the build (fan-out caps, skipping per-skill
  web research at scale, the resume-from-step mechanism, per-item commits).
- Review and acceptance of every module.

**Implemented with heavy Claude Code assistance:**
- All Python modules (`app/`), the React UI (`web/`), the pipeline, cascade
  reasoner, and CLI.
- The prompts in `app/ai/analysts.py` and the retry/rate-pacing logic in
  `app/ai/llm.py`.
- All documentation in `docs/`.

## How to verify understanding of each component

Every module has a top-of-file docstring explaining its role. Every LLM call the
application makes is logged verbatim (prompt, response, tokens) to
`data/llm_log.db` — `select purpose, count(*) from llm_calls group by purpose`
shows exactly which decision each prompt drove.

Key components to be able to explain in the demo:
- `app/models.py` — why one `edges` table, why overlays are separate, the evidence tables.
- `app/graph/traverse.py` — the single neighbour query that everything is built on.
- `app/pipeline/ingest.py` — the 9 steps, why each commits per item (resumability).
- `app/pipeline/cascade.py` — bounded BFS + one LLM judgement per hop; not a single prompt.
- `app/graph/rollup.py` — the graph-derived role / process overlays (no LLM).
- `app/ai/llm.py` — structured output, validation-retry, rate pacing, audit logging.

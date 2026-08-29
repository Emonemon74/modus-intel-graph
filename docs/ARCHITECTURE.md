# Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ USER INTERFACE                                                 │
│ React + Vite + Cytoscape.js  (web/)                            │
│  • Explorer  — node list, graph canvas, entity panel, evidence │
│  • Cascade   — pick a node + hypothesis, see knock-on impact   │
│  • Add       — the "surprise record" live-analysis form        │
│  • Jobs      — pipeline progress                               │
└───────────────┬───────────────────────────────────────────────┘
                │  JSON / REST
┌───────────────┴───────────────────────────────────────────────┐
│ APPLICATION / API LAYER                                        │
│ FastAPI  (app/api/main.py)  — thin; delegates to pipeline/graph│
│  /ingest  /entities  /nodes  /graph  /cascade  /evidence  /jobs│
└───────────────┬───────────────────────────────────────────────┘
┌───────────────┴───────────────────────────────────────────────┐
│ AI INTELLIGENCE LAYER  (app/ai/, app/pipeline/)                │
│  • llm.py        one OpenAI-compatible entry point:            │
│                  structured JSON out, retry, rate-pacing,      │
│                  every call logged (prompt+response+tokens)    │
│  • analysts.py   one prompt-function per reasoning step        │
│  • embeddings.py MiniLM (local, CPU) + FAISS inner-product     │
│  • pipeline/     ingest (9 steps) · cascade reasoner ·         │
│                  add_entity (live) · research · evidence       │
└───────────────┬───────────────────────────────────────────────┘
┌───────────────┴───────────────────────────────────────────────┐
│ DATA & KNOWLEDGE LAYER  (app/models.py, SQLAlchemy)            │
│  SQLite (default) / Postgres (one env var)                     │
│  • node tables: industries, stages, processes, activities,     │
│                 roles, skills                                  │
│  • edges:       ONE typed table for every relationship         │
│  • overlays:    ai_opportunities, skill_impacts,               │
│                 cascade_runs / cascade_results                 │
│  • evidence:    sources, claim_evidence                        │
│  • operational: jobs (resumable), llm_calls (audit)            │
│  FAISS index file: research-snippet vectors for retrieval      │
└───────────────┬───────────────────────────────────────────────┘
┌───────────────┴───────────────────────────────────────────────┐
│ EXTERNAL RESEARCH / DATA                                       │
│  DuckDuckGo web search (no key)  +  local corpus/ (PDF, txt)   │
│  every snippet stored as a `sources` row before use            │
└───────────────────────────────────────────────────────────────┘
```

## Request flows

**Build graph** — `POST /ingest {industry}`
→ 9-step pipeline, each step: read worklist (short txn) → per item: LLM call →
write in its own txn → next. Crash-safe: rerun resumes.

**Surprise record** — `POST /entities {type,name,context}`
→ insert node → run only the steps relevant to that type (reusing the same
functions as bulk ingest) → return the new sub-graph. Fan-out capped so it
finishes in under a minute for a live demo.

**Cascade** — `POST /cascade {trigger_type, trigger_id, hypothesis}`
→ bounded breadth-first walk from the trigger. At each hop the LLM judges
"is this neighbour materially affected?" given the hypothesis + retrieved
evidence. Material nodes are recorded (`cascade_results`) and expanded further,
up to `CASCADE_MAX_DEPTH`.

**Evidence** — every overlay row and cascade result has `claim_evidence` rows
linking it to the `sources` snippets (with similarity score) that back it.

## Technology choices & fallbacks

| Component | Choice | Licence | If it goes away |
|---|---|---|---|
| LLM | `openai/gpt-oss-120b` via Groq free tier | Apache-2.0 (weights) | point `LLM_BASE_URL` at local Ollama |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Apache-2.0 | already local |
| Vector search | FAISS | MIT | already local |
| DB | SQLite / SQLAlchemy | PD / MIT | swap `DATABASE_URL` to Postgres |
| API | FastAPI + Uvicorn | MIT | — |
| UI | React, Vite, Cytoscape.js | MIT | — |
| Web research | duckduckgo-search | MIT | degrades to local corpus only |

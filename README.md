# Process × Role × Skill Intelligence Graph

MODUS Enterprise AI Build Challenge — **Assignment 11**.

A connected-intelligence application for one industry (default: **Retail Banking**).
It independently researches and builds a graph:

```
Industry → Value-Chain Stage → Process → Activity → Role → Skill
```

then overlays, for every node, an **AI opportunity** assessment and a **future-skill
classification**, each traceable to stored research evidence. You can navigate the
relationships, add a brand-new process/role/skill and have it analysed live, and
run a **cascade**: "if AI automates this activity, what is the knock-on impact on
roles and skills?"

## Architecture

| Layer | This project |
|---|---|
| **UI** | React + Vite + Cytoscape.js graph explorer (`web/`) |
| **API** | FastAPI (`app/api/`) |
| **AI intelligence** | OpenAI-compatible LLM (structured JSON output) + local MiniLM embeddings + FAISS retrieval (`app/ai/`) |
| **Data & knowledge** | SQLite via SQLAlchemy — nodes, one typed `edges` table, overlay + evidence tables (`app/models.py`). Swap to Postgres with one env var. |
| **External research** | DuckDuckGo web search + a local PDF/text corpus (`corpus/`), all snippets persisted as `sources` |

See `docs/ARCHITECTURE.md` and `docs/DATA_MODEL.md`.

## Setup

Requires Python 3.13 + [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
# 1. install
uv sync
cp .env.example .env        # then put an LLM key in .env  (see below)

# 2. build the seed graph  (~15-20 min on the free tier; resumable)
uv run python -m app.cli ingest "Retail Banking"

# 3. run the API
uv run uvicorn app.api.main:app --port 8000

# 4. run the UI
cd web && npm install && npm run dev      # http://localhost:5173
#   or build it and let the API serve it:  npm run build  -> http://localhost:8000
```

### LLM configuration

The app talks to any **OpenAI-compatible** chat endpoint. Default is Groq's free
tier serving `openai/gpt-oss-120b` (open-weight, Apache-2.0).

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your free key from https://console.groq.com>
LLM_MODEL=openai/gpt-oss-120b
```

**If that service becomes paid/unavailable:** install [Ollama](https://ollama.com),
`ollama pull llama3.1:8b`, and set:

```
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1:8b
LLM_TOKENS_PER_MIN=0        # no client-side pacing needed locally
```

Nothing else changes — embeddings, vector search and the database are already
fully local.

## CLI

```bash
uv run python -m app.cli ingest "Retail Banking"              # build the graph
uv run python -m app.cli ingest "Retail Banking" --from analyse  # resume from a step
uv run python -m app.cli reindex                              # rebuild FAISS from `sources`
uv run python -m app.cli export                               # dump graph -> data/sample_graph.json
uv run python -m app.cli stats                                # counts
uv run python -m app.cli reset                                # wipe graph, keep schema
```

Ingest steps (for `--from`): `industry_stages, processes, activities, roles,
role_activity, skills, research, analyse, classify`.

## Key API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | build the graph for an industry |
| POST | `/entities` | add a process/role/skill and analyse it live (the "surprise record" test) |
| GET | `/nodes/{type}` / `/nodes/{type}/{id}` | list / detail with neighbours + overlays |
| GET | `/graph?focus_type=&focus_id=&depth=` | subgraph for the visualiser |
| POST | `/cascade` + GET `/cascade/{id}` | run and read a cascading-impact analysis |
| GET | `/evidence/{claim_type}/{id}` | the research snippets behind any AI claim |

## How it scales ("1,000 processes tomorrow")

- The graph schema is fixed; more processes = more rows in `processes` / `edges`,
  indexed on `(source_type, source_id)` and `(target_type, target_id)`.
- Ingest is a resumable, item-at-a-time job (`jobs` table) — kill it and rerun.
- Skill nodes are de-duplicated by embedding similarity so N processes don't
  explode into N×k near-identical skills.
- Traversal and cascade use one uniform neighbour query regardless of node kind.
- The only throughput limit is the LLM; raise `LLM_TOKENS_PER_MIN`, parallelise
  workers, or point at a local model.

## What was AI-assisted

Development used an AI coding assistant. Every module has a docstring explaining
its role; every LLM call the app makes is logged to `data/llm_log.db`
(`llm_calls` table) with the exact prompt, response and token counts.

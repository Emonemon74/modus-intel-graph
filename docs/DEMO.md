# Live demo runbook (10–15 min)

## Before the session

```bash
cd modus-intel-graph
git pull
uv run python -m app.cli load-sample        # full graph + overlays + a pre-computed cascade
cd web && npm run build && cd ..
uv run uvicorn app.api.main:app --port 8000
```

Open **http://localhost:8000**. Have a second terminal ready showing:
```
sqlite3 data/llm_log.db "select purpose, count(*) from llm_calls group by purpose;"
```

**Timing note:** the free Groq tier queues requests, so a *live* AI action takes
30–90 s. Talk through the architecture while it runs. The graph, all overlays,
evidence, and one cascade are pre-loaded and instant. Keep the run to ONE fresh
browser session — don't pre-click things that spend the token budget.

---

## 1 · Problem & architecture (2 min)

- Open `docs/architecture.svg`. Five layers, each a real component; candidates
  chose their own — this one is FastAPI + SQLite + FAISS + an OpenAI-compatible LLM.
- "The graph is **not fixture data** — a 9-step pipeline researched and built it.
  Every AI claim links to a stored source, and every model call is logged."
  → run the `llm_calls` query in terminal 2: ~470 calls, grouped by purpose.

## 2 · Navigate the connected graph (3–4 min) — all instant

- **Explorer** → pick process **Automated Risk Scoring**.
  - Right panel: **Process AI Roll-up** — score 0.88, 3 of 4 activities automatable,
    **Affected roles (5)** listed directly (answers "select a process → see roles").
  - "These numbers are computed from the graph on read — no LLM — so every one is
    checkable against the rows it counts."
- Click activity **Model execution** → **AI Opportunity** (AUTOMATE, benefit, risk,
  confidence) → **Show evidence** → snippets with similarity scores + source URLs
  (one is an OCC Comptroller's Handbook).
- Click a **skill** (e.g. *Statistical Modeling*) → **Skill Impact** classification
  + evidence.
- Click a **role** (e.g. *Loan Officer – Consumer Lending*) → **Future Change**
  panel: AI-exposure band, activity breakdown (automate/augment), skill breakdown
  (declining/emerging), all graph-derived.
- Click a skill → its `ROLE_HAS_SKILL` neighbours = "every role that needs this skill".

## 3 · Cascading impact (2–3 min)

- **Cascade** tab → trigger **activity / Model execution**, hypothesis
  *"AI fully automates this activity"*, **depth 1**, Run.
  - ~30–60 s. While it runs: "this isn't one prompt — it walks the graph and asks
    the model one question per hop: is this neighbour materially affected?"
  - Result: direct impacts on skills, the parent process, and the CTO role, each
    with reasoning + the graph path.
- Then: "it recurses — here's the same trigger at depth 2 I ran earlier"
  → the pre-loaded run shows 16 impacts down to depth 2 (Model execution →
  Statistical Modeling → Model calibration, etc.). *(In the UI, re-run at depth 2
  only if you have 2 min to spare; otherwise describe it from the loaded data.)*

## 4 · The surprise-record test (3 min) — hand control to the panel

- **Add** tab. Ask a judge to name any Retail Banking **process, role, or skill**
  not in the list.
- Enter it. 60–90 s. It is inserted, broken into activities, skills attached and
  de-duplicated against existing ones, existing roles linked, an AI-opportunity
  assessment generated.
- Switch to **Explorer**, open the new node, show its neighbours + overlay.
- Optionally run a depth-1 **Cascade** on it.

## 5 · Scale (1 min)

- README "How it scales" + `docs/ARCHITECTURE.md`.
- "One `edges` table, indexed both directions; ingest is a resumable per-item job;
  skills de-duped by embedding similarity so N processes don't explode into N×k
  skills; traversal and cascade use one neighbour query. The only throughput limit
  is the LLM — raise the rate cap, add workers, or point `LLM_BASE_URL` at a local
  Ollama. Storage → change `DATABASE_URL` to Postgres, no code change."

## If Groq is unreachable mid-demo

Show `.env.example` → change the 3 Ollama lines → `ollama serve`. Same code path.
The pre-loaded graph, overlays, evidence and cascade stay fully browsable regardless.

## What to be ready to explain (judges will probe)

| Component | One-liner |
|---|---|
| `app/models.py` | one typed `edges` table → uniform traversal, scales by rows not tables |
| `app/graph/traverse.py` | the single neighbour query everything is built on |
| `app/pipeline/ingest.py` | 9 steps, each commits per item → crash-resumable |
| `app/pipeline/cascade.py` | bounded BFS + one LLM judgement per hop |
| `app/graph/rollup.py` | role/process overlays computed from the graph, no LLM |
| `app/ai/llm.py` | structured JSON output, validation-retry, rate pacing, audit log |

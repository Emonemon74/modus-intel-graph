# 10–15 minute live demo script

## 0. Before the panel arrives
```bash
uv run uvicorn app.api.main:app --port 8000      # serves the built UI too
```
Open `http://localhost:8000`. Graph already ingested for **Retail Banking**.

## 1. The problem & the architecture (2 min)
- Show `docs/ARCHITECTURE.md`. Four layers, each a real component.
- "The graph is not fixture data — it was researched and built by the pipeline.
  Every AI claim links to stored evidence, and every LLM call is logged."
- Show `data/llm_log.db` count / one row.

## 2. Navigate the connected graph (3 min)
- **Explorer** tab. Pick a Process (e.g. *Loan Application Evaluation*).
  Graph shows stage → process → activities → roles → skills.
- Click an **Activity** → entity panel shows the **AI Opportunity**
  (AUTOMATE/AUGMENT + benefit/risk/confidence). Hit **Show evidence** →
  research snippets with similarity scores + source URLs.
- Click a **Skill** → **Skill Impact** classification (e.g. DECLINING) + evidence.
- Click a **Role** → see every process/activity/skill it touches.
- "Select a skill → see every role that needs it" — pick a skill, read
  `ROLE_HAS_SKILL` / `ACTIVITY_REQUIRES_SKILL` neighbours.

## 3. Cascading impact (3 min)
- **Cascade** tab. Trigger = an Activity with high automation potential.
  Hypothesis: *"AI fully automates this activity."* Run.
- Walk the output: affected **roles** → their other **activities** →
  **skills** that rise/fall, each with reasoning and the graph path.
- "This is derived by walking the graph and reasoning at each hop — not one
  giant prompt."

## 4. The surprise-record test (3 min) — hand control to the panel
- **Add** tab. Ask the panel to name any Retail Banking process, role, or skill
  **not** already in the list.
- Enter it. ~30–60s. It's inserted, broken into activities, skills attached,
  roles linked, AI opportunity + evidence generated.
- Switch to **Explorer**, open the new node, show its neighbours and overlay.
- Run a **Cascade** on the brand-new node.

## 5. Scale question (1 min)
- `docs/ARCHITECTURE.md` + README "How it scales" section.
- Fixed schema; `edges` table + indexes; resumable per-item job; embedding-based
  skill dedup; uniform traversal; LLM is the only throughput limit and is
  swappable / parallelisable.

## Fallback talking point
If Groq is unreachable during the demo: show `.env.example`, change 3 lines to
the Ollama block, `ollama serve` — same code path.

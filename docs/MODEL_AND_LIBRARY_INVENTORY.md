# Model & library inventory

Everything here is free / open-source / free-tier / locally runnable. No paid licence
is required to run or evaluate this project.

## Models

| Model | Role | Access | Licence | Fallback |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | all reasoning/extraction/classification | Groq free tier (OpenAI-compatible API) | **Apache-2.0** (open weights) | run locally via Ollama (`gpt-oss:20b` / `llama3.1:8b`); only `LLM_BASE_URL`+`LLM_MODEL` change |
| `sentence-transformers/all-MiniLM-L6-v2` | text embeddings for evidence retrieval + skill dedup | downloaded once from HuggingFace, then fully local (CPU) | **Apache-2.0** | already local |

The app is model-agnostic: it uses the OpenAI chat-completions protocol, so any
compatible endpoint (OpenAI, Together, Fireworks, local Ollama / llama.cpp) works.

## Python libraries

| Library | Version | Purpose | Licence |
|---|---|---|---|
| fastapi | 0.141.1 | API layer | MIT |
| uvicorn | 0.52.4 | ASGI server | BSD-3 |
| sqlalchemy | 2.0.52 | ORM / DB abstraction | MIT |
| pydantic | 2.13.5 | data validation, LLM output schemas | MIT |
| pydantic-settings | 2.15.0 | env-driven config | MIT |
| openai | 3.6.0 | OpenAI-compatible client | Apache-2.0 |
| sentence-transformers | 6.0.0 | embedding model runner | Apache-2.0 |
| faiss-cpu | 1.15.0 | vector similarity search | MIT |
| numpy | 2.5.2 | vector math | BSD-3 |
| torch | 2.13.0 | embedding model backend | BSD-3 |
| transformers | 5.16.1 | embedding model backend | Apache-2.0 |
| httpx | 0.28.1 | HTTP client | BSD-3 |
| ddgs | 9.16.0 | DuckDuckGo web search (no API key) | MIT |
| wikipedia-api | 0.15.0 | Wikipedia research source | MIT |
| pypdf | 6.16.2 | read local corpus PDFs | BSD-3 |
| tenacity | 9.1.4 | retry logic | Apache-2.0 |
| python-dotenv | 1.2.3 | .env loading | BSD-3 |

## JavaScript libraries

| Library | Purpose | Licence |
|---|---|---|
| react / react-dom | UI | MIT |
| vite | build tool / dev server | MIT |
| cytoscape | graph visualisation | MIT |

## Data

- No proprietary datasets. The seed graph is **generated at ingest time** by the
  pipeline (LLM + web research), not shipped as fixture data.
- Research snippets come from public web search + any PDFs the user drops in
  `corpus/`. Each is stored in the `sources` table with its URL/title.
- A synthetic/sample export of a built graph is in `data/sample_graph.json`.

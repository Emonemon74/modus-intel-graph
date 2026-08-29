"""Central configuration.

Everything that might change between "my laptop", "a reviewer's laptop", and
"fully offline" lives here as an environment variable with a sane default.
This is what lets us answer the challenge question
"what happens if your hosted LLM goes away?" -> change LLM_BASE_URL to a local
Ollama endpoint and nothing else in the codebase moves.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Data & knowledge layer -------------------------------------------------
    # SQLite by default = zero infra for a reviewer. Swap to
    # postgresql+psycopg://user:pass@host/db and the ORM code is unchanged.
    database_url: str = "sqlite:///./data/graph.db"
    faiss_index_path: str = "./data/faiss.index"
    faiss_meta_path: str = "./data/faiss_meta.json"

    # --- AI intelligence layer ------------------------------------------------
    # OpenAI-compatible endpoint. Works with Groq, OpenAI, Together, or a local
    # Ollama server (http://localhost:11434/v1). Only the URL + key + model change.
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"  # open-weight (Apache-2.0), served on Groq free tier
    # gpt-oss is a reasoning model; "low" keeps hidden reasoning tokens small so we
    # fit the free-tier 8k tokens/min budget. Ignored by models that don't support it.
    llm_reasoning_effort: str = "low"
    llm_max_retries: int = 10
    llm_timeout: float = 45.0   # per-request; a queued free-tier call that exceeds this is retried
    # Client-side tokens-per-minute cap. Groq free tier for gpt-oss-120b is 8000.
    # Set to 0 to disable (local Ollama, or a paid tier).
    llm_tokens_per_min: int = 6000

    # Local, CPU-friendly embedding model (Apache-2.0). Downloaded once, then offline.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- External research --------------------------------------------------
    enable_web_search: bool = True        # flip off to run purely on local corpus
    corpus_dir: str = "./corpus"
    max_sources_per_entity: int = 4

    # --- Pipeline fan-out limits ------------------------------------------
    # Caps keep the seed graph finishable and the live "surprise record" test fast.
    max_processes_per_stage: int = 5
    max_activities_per_process: int = 5
    max_skills_per_activity: int = 4
    max_roles: int = 20
    max_research_skills: int = 25   # research only the most-connected skills (web search per skill doesn't scale)
    cascade_max_depth: int = 2
    cascade_max_branch: int = 5   # neighbours probed per node -- keeps a live cascade ~1 min

    # Tighter caps for the live "surprise record" path so it returns in ~30-60s.
    live_max_activities: int = 3
    live_max_skills_per_activity: int = 2
    live_research: bool = False    # skip web research on live-add for speed


settings = Settings()

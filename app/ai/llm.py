"""The AI intelligence layer's front door.

One function -- `complete_json` -- is used by every pipeline step. It:
  1. calls an OpenAI-compatible chat endpoint (Groq / OpenAI / local Ollama),
  2. forces the reply to be valid JSON matching a Pydantic schema,
  3. retries on transient errors, on rate limits (respecting Retry-After),
     and on malformed JSON (feeding the validation error back to the model),
  4. logs every call -- prompt, response, tokens, latency -- to its own DB file.
  5. throttles proactively to stay under a tokens-per-minute budget.

Keeping this in ONE place is what makes the whole app portable and auditable.
"""

import json
import re
import threading
import time
from typing import TypeVar

from openai import APIError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import LLMCall

# The audit log lives in its OWN sqlite file so writing a log row can never
# contend with an open pipeline transaction on the main graph DB. For Postgres
# (real concurrency) we just reuse the main database.
if settings.database_url.startswith("sqlite"):
    _log_engine = create_engine("sqlite:///./data/llm_log.db",
                                connect_args={"check_same_thread": False}, future=True)
else:
    _log_engine = create_engine(settings.database_url, future=True)
LLMCall.__table__.create(bind=_log_engine, checkfirst=True)
_LogSession = sessionmaker(bind=_log_engine, future=True)

_client = OpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key or "not-needed-for-local",
    max_retries=0,  # we do our own ret/logging
)

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------------- #
# Client-side pacing -- keeps free-tier Groq (8k tokens/min) happy.           #
# A simple fixed gap between calls: budget / avg-tokens-per-call => calls/min. #
# Predictable, and a 429 just means we wait the Retry-After and carry on.      #
# --------------------------------------------------------------------------- #
class _Pacer:
    def __init__(self, tokens_per_min: int, avg_tokens: int = 650) -> None:
        self.min_gap = 0.0 if tokens_per_min <= 0 else 60.0 / max(1, tokens_per_min / avg_tokens)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            gap = time.time() - self._last
            if gap < self.min_gap:
                time.sleep(self.min_gap - gap)
            self._last = time.time()


_pacer = _Pacer(settings.llm_tokens_per_min)


def _log_call(purpose, system, user, response, usage, latency_ms) -> None:
    s = _LogSession()
    try:
        s.add(LLMCall(
            purpose=purpose, model=settings.llm_model,
            system_prompt=system, user_prompt=user, response=response,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        ))
        s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()


def _retry_after_seconds(err: Exception) -> float:
    m = re.search(r"try again in ([\d.]+)s", str(err))
    return min(float(m.group(1)) + 1.0, 65.0) if m else 12.0


def _raw_chat(system: str, user: str) -> tuple[str, object]:
    """One API call with rate-limit-aware retries. The free tier's tokens-per-minute
    limit is a rolling window, so on repeated 429s we back off toward a full minute."""
    for attempt in range(settings.llm_max_retries):
        _pacer.wait()
        try:
            kwargs = dict(
                model=settings.llm_model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            if settings.llm_reasoning_effort:
                kwargs["reasoning_effort"] = settings.llm_reasoning_effort
            resp = _client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or "", resp.usage
        except RateLimitError as e:
            wait = _retry_after_seconds(e)
            if attempt >= 3:            # window still saturated -> wait out a full minute
                wait = max(wait, 62.0)
            time.sleep(wait)
        except APIError as e:
            if attempt == settings.llm_max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("exhausted retries on rate limit")


# A compact JSON skeleton with the EXACT keys -- unambiguous but ~5x smaller
# than dumping the full JSON Schema. Placeholder values carry the field's
# description so the model knows what to put there.
def _skeleton(schema_json: dict, defs: dict) -> object:
    if "$ref" in schema_json:
        return _skeleton(defs[schema_json["$ref"].split("/")[-1]], defs)
    t = schema_json.get("type")
    if t == "object":
        return {k: _skeleton(v, defs) for k, v in schema_json.get("properties", {}).items()}
    if t == "array":
        return [_skeleton(schema_json.get("items", {}), defs)]
    if t == "number" or t == "integer":
        return schema_json.get("description", "0..1") or 0
    if t == "boolean":
        return schema_json.get("description", "true|false")
    return schema_json.get("description", "text") or "text"


def _skeleton_hint(schema: type[BaseModel]) -> str:
    full = schema.model_json_schema()
    return json.dumps(_skeleton(full, full.get("$defs", {})), separators=(",", ":"))


def complete_json(purpose: str, system: str, user: str, schema: type[T]) -> T:
    """Return an instance of `schema`, or raise after exhausting retries.

    `purpose` is a short tag ('extract_stages', 'analyse_activity', ...) logged
    with every call so a reviewer can trace every decision the AI made.
    """
    contract = (
        f"{system}\nReturn ONLY a JSON object with EXACTLY this shape "
        f"(replace the placeholder strings with real values, keep all keys verbatim):\n"
        f"{_skeleton_hint(schema)}"
    )
    last_err: Exception | None = None
    for _ in range(3):
        t0 = time.time()
        content, usage = _raw_chat(contract, user)
        _log_call(purpose, contract, user, content, usage, int((time.time() - t0) * 1000))
        try:
            return schema.model_validate_json(content)
        except ValidationError as e:
            last_err = e
            user = f"{user}\n\nPrevious reply was invalid ({e}). Return corrected JSON only."
    raise RuntimeError(f"{purpose}: no valid JSON after retries: {last_err}")

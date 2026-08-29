"""External research -> Source rows -> FAISS index.

For each entity (a process, a skill) we gather a few short text snippets from:
  - the local corpus/  folder (PDFs / .txt you curated -- always available), and
  - a live web search (DuckDuckGo, no API key) when ENABLE_WEB_SEARCH is on.

Every snippet is persisted as a Source and embedded. Nothing here is required to
succeed -- if the network is down we degrade to corpus-only, and if the corpus is
empty we mark findings as 'reasoned' rather than evidence-backed.
"""

import glob
import os

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.ai.embeddings import EvidenceIndex
from app.config import settings
from app.models import Source

_corpus_cache: list[dict] | None = None


def _load_corpus() -> list[dict]:
    """Read every PDF/txt in corpus/ once, split into ~1200-char chunks."""
    global _corpus_cache
    if _corpus_cache is not None:
        return _corpus_cache
    chunks: list[dict] = []
    for path in glob.glob(os.path.join(settings.corpus_dir, "*")):
        name = os.path.basename(path)
        if name.lower() == "readme.md" or name.startswith((".", "_")):
            continue  # housekeeping files are not research
        try:
            if path.lower().endswith(".pdf"):
                text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            elif path.lower().endswith((".txt", ".md")):
                text = open(path, encoding="utf-8", errors="ignore").read()
            else:
                continue
        except Exception:
            continue
        for i in range(0, len(text), 1200):
            piece = text[i : i + 1200].strip()
            if len(piece) > 200:
                chunks.append({"title": name, "publisher": "local corpus",
                               "url": f"file://{name}", "text": piece})
    _corpus_cache = chunks
    return chunks


def _corpus_matches(query: str, limit: int) -> list[dict]:
    q = set(query.lower().split())
    scored = []
    for c in _load_corpus():
        overlap = len(q & set(c["text"].lower().split()))
        if overlap:
            scored.append((overlap, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:limit]]


def _web_matches(query: str, limit: int) -> list[dict]:
    if not settings.enable_web_search:
        return []
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit))
        return [
            {"title": r.get("title", ""), "publisher": r.get("href", ""),
             "url": r.get("href", ""), "text": r.get("body", "")}
            for r in results if r.get("body")
        ]
    except Exception:
        return []  # offline / rate-limited -> corpus only


def research_entity(s: Session, topic: str, index: EvidenceIndex) -> list[int]:
    """Gather snippets about `topic`, persist as Source rows, embed. Return source ids."""
    limit = settings.max_sources_per_entity
    found = _corpus_matches(topic, limit) + _web_matches(topic, limit)
    if not found:
        return []

    source_ids, to_embed = [], []
    for item in found[: limit * 2]:
        src = Source(
            url=item["url"][:1000], title=item["title"][:500],
            publisher=item["publisher"][:300],
            kind="corpus" if item["url"].startswith("file://") else "web",
            raw_excerpt=item["text"][:2000],
        )
        s.add(src)
        s.flush()
        source_ids.append(src.id)
        to_embed.append({"source_id": src.id, "text": item["text"][:2000]})

    index.add(to_embed)
    return source_ids

"""Local embeddings + FAISS vector index for evidence retrieval.

Why we need this: when the AI analyses an activity or classifies a skill, it must
cite evidence. We embed every research snippet once, then for each claim we pull
the top-k most similar snippets and attach them as ClaimEvidence. This is
retrieval-augmented generation scoped to our own knowledge base -- not "ChatGPT
with web search".

All of this runs on CPU, offline, after the model downloads once.
"""

import json
import os
import threading

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    vecs = _get_model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vecs.astype("float32")


class EvidenceIndex:
    """Thin wrapper over a FAISS inner-product index + a parallel metadata list.

    Because vectors are L2-normalised, inner product == cosine similarity.
    """

    def __init__(self) -> None:
        self.index = faiss.IndexFlatIP(settings.embedding_dim)
        self.meta: list[dict] = []  # meta[i] describes vector i: {source_id, text}
        self._load()

    def _load(self) -> None:
        if os.path.exists(settings.faiss_index_path) and os.path.exists(settings.faiss_meta_path):
            self.index = faiss.read_index(settings.faiss_index_path)
            with open(settings.faiss_meta_path) as f:
                self.meta = json.load(f)

    def save(self) -> None:
        faiss.write_index(self.index, settings.faiss_index_path)
        with open(settings.faiss_meta_path, "w") as f:
            json.dump(self.meta, f)

    def add(self, items: list[dict]) -> None:
        """items: [{"source_id": int, "text": str}, ...]"""
        if not items:
            return
        vecs = embed([it["text"] for it in items])
        self.index.add(vecs)
        self.meta.extend(items)

    def search(self, query: str, k: int = 4) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        scores, idx = self.index.search(embed([query]), min(k, self.index.ntotal))
        out = []
        for score, i in zip(scores[0], idx[0]):
            if i == -1:
                continue
            hit = dict(self.meta[i])
            hit["relevance"] = float(score)
            out.append(hit)
        return out

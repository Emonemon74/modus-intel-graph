"""Turn a free-text claim into ClaimEvidence rows by retrieving the most similar
research snippets from the FAISS index and recording the match + score.
"""

from sqlalchemy.orm import Session

from app.ai.embeddings import EvidenceIndex
from app.models import ClaimEvidence


def attach_evidence(s: Session, index: EvidenceIndex, claim_type: str, claim_id: int,
                    query: str, k: int = 3, min_relevance: float = 0.25) -> str:
    """Record evidence for a claim and return a text block to feed back into
    later prompts (so the analysis is visibly grounded)."""
    hits = index.search(query, k=k)
    lines = []
    for h in hits:
        if h["relevance"] < min_relevance:
            continue
        s.add(ClaimEvidence(
            claim_type=claim_type, claim_id=claim_id, source_id=h["source_id"],
            quote=h["text"][:600], relevance=h["relevance"],
        ))
        lines.append(f"- ({h['relevance']:.2f}) {h['text'][:300]}")
    return "\n".join(lines)

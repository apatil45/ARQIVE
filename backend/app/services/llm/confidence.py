"""
Confidence score: 0.5 * avg cosine + 0.3 * LLM self-reported + 0.2 * citation coverage.
"""
from __future__ import annotations


HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.50


def compute_confidence(
    top_chunk_scores: list[float],
    llm_confidence: str | None,
    citation_coverage: float,
) -> tuple[float, str]:
    """
    Returns (score 0-1, reason string).
    llm_confidence: "HIGH"|"MEDIUM"|"LOW" from LLM JSON.
    citation_coverage: fraction of provided chunks that were cited.
    """
    avg_sim = sum(top_chunk_scores) / len(top_chunk_scores) if top_chunk_scores else 0.0
    llm_score = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}.get((llm_confidence or "").upper(), 0.0)
    score = 0.5 * avg_sim + 0.3 * llm_score + 0.2 * citation_coverage
    if score >= HIGH_THRESHOLD:
        reason = "High relevance and citation coverage."
    elif score >= MEDIUM_THRESHOLD:
        reason = "Moderate relevance; verify key figures."
    else:
        reason = "Low relevance or citation coverage; manual verification recommended."
    return round(score, 3), reason


def confidence_label(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"

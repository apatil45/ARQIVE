"""
Reciprocal Rank Fusion: merge semantic + structured result lists into top-5.
k=60. score(doc) = sum(1 / (60 + rank_i(doc))) per list i.
"""
from __future__ import annotations

from typing import Any

RRF_K = 60
TOP_N = 5


def reciprocal_rank_fusion(
    semantic_results: list[dict[str, Any]],
    structured_results: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[dict[str, Any]]:
    """
    Merge by chunk id. Each list contributes 1/(k+rank). Return top_n by combined score.
    Prefer semantic for full text when present.
    """
    scores: dict[str, float] = {}
    by_id: dict[str, dict[str, Any]] = {}

    for rank, item in enumerate(semantic_results):
        ch_id = item.get("id") or ""
        if not ch_id:
            continue
        scores[ch_id] = scores.get(ch_id, 0) + 1.0 / (RRF_K + rank + 1)
        by_id[ch_id] = item

    for rank, item in enumerate(structured_results):
        ch_id = item.get("id") or ""
        if not ch_id:
            continue
        scores[ch_id] = scores.get(ch_id, 0) + 1.0 / (RRF_K + rank + 1)
        if ch_id not in by_id:
            by_id[ch_id] = item

    sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])
    out = []
    for ch_id in sorted_ids[:top_n]:
        out.append(by_id[ch_id])
    return out

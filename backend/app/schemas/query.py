"""Query request/response schemas."""
from __future__ import annotations


from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str


class CitationItem(BaseModel):
    doc_id: str
    filename: str
    page: int
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    confidence: str
    confidence_reason: str
    unanswered_aspects: str | None = None

"""Query API: requires auth and returns structure."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_query_stream_requires_auth(async_client: AsyncClient) -> None:
    r = await async_client.get("/api/query/stream", params={"q": "test"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_query_history_requires_auth(async_client: AsyncClient) -> None:
    r = await async_client.get("/api/query/history")
    assert r.status_code == 401

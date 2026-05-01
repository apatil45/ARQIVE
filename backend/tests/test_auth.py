"""
Auth API tests: login, me, refresh, logout.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/login",
        json={"email": "auditor@test.arqive.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["email"] == "auditor@test.arqive.com"
    assert data["role"] == "auditor"
    assert "refresh_token" in r.cookies or "Set-Cookie" in r.headers


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/login",
        json={"email": "auditor@test.arqive.com", "password": "Wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.arqive.com", "password": "any"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient) -> None:
    login = await client.post(
        "/api/auth/login",
        json={"email": "auditor@test.arqive.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "auditor@test.arqive.com"


@pytest.mark.asyncio
async def test_refresh(client: AsyncClient) -> None:
    login = await client.post(
        "/api/auth/login",
        json={"email": "auditor@test.arqive.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200
    # Client should have refresh cookie set
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["email"] == "auditor@test.arqive.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/login",
        json={"email": "auditor@test.arqive.com", "password": "TestPass123!"},
    )
    r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json()["message"] == "Logged out"
    # Refresh should fail after logout
    r2 = await client.post("/api/auth/refresh")
    assert r2.status_code == 401

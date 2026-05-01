# ARQIVE

AI-powered audit document intelligence platform. On-premise, no cloud API calls.

## Requirements

- **Python 3.11** (required for backend; 3.12+ has compatibility issues with SQLAlchemy/Alembic)
- Docker & Docker Compose (recommended)
- Ollama with `llama3.2:3b` for RAG queries

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env: APP_SECRET_KEY (min 32 chars), DATABASE_URL=sqlite+aiosqlite:///./data/arqive_dev.db

docker compose up --build
# In another terminal:
make init-db
make seed-demo
make pull-model
```

- **Frontend:** http://localhost:3000 (Login → Search, Documents, Admin)
- **API:** http://localhost:8000 — health: `/api/health`, ready: `/api/health/ready`
- **Production stack template:** `docker compose -f docker-compose.prod.yml up -d`

**Demo users (after seed-demo):**
- viewer@demo.arqive.com / DemoViewer123!
- auditor@demo.arqive.com / DemoAuditor123!
- admin@demo.arqive.com / DemoAdmin123!

## What’s included

- **Backend:** FastAPI, JWT auth (access + httpOnly refresh), RBAC (viewer/auditor/admin)
- **Documents:** Upload (PDF, Word, Excel, CSV) → Celery ingestion → ChromaDB + SQLite
- **Query:** Semantic + structured retrieval, RRF rerank, Ollama (llama3.2:3b), SSE streaming, citations, confidence
- **Audit:** Append-only log with row hash; admin audit-log endpoint
- **Frontend:** React + Vite + Tailwind, Login, Search (SSE), Documents, Admin

See `.cursorrules` for full stack, schema, and build order.

## Notes

- Demo users are created by `make seed-demo` (startup no longer auto-seeds users).
- Local non-Docker test/lint commands require Python `3.11` and installed dependencies.

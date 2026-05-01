# ARQIVE backend. Python 3.11 only (per .cursorrules).
FROM python:3.11-slim

WORKDIR /app

# Install deps (PyTorch CPU later if needed for embeddings)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app

# Default: run API (override in compose for worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

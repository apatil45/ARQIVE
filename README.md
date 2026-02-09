# ARQIVE

**A**udit-document **R**etrieval and **Q**uery **I**ntelligence **V**ia **E**mbeddings

A document Q&A app that runs locally. Upload PDFs, DOCX, or text; ask questions; get answers with sources. No cloud—everything stays on your machine.

## Requirements

- Python 3.9+
- Node.js 18+
- [Ollama](https://ollama.ai) (with a model, e.g. `ollama pull tinyllama`)

## Setup

**Backend**

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Server runs at `http://0.0.0.0:8000`.

**Frontend** (new terminal)

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:3000`. Default login: `admin` / `admin`. Change this for any real use.

## Usage

Upload documents from the Upload page. Use Chat to ask questions; answers include source references.

## Troubleshooting

- **Ollama errors:** Ensure Ollama is running (`ollama serve`) and the model is installed (`ollama pull tinyllama`).
- **Backend:** Activate the venv and reinstall deps if needed: `pip install -r requirements.txt`.
- **Frontend:** Backend must be running; ensure port 3000 is free.

## Structure

- `backend/` — Python API, RAG, auth, document ingest
- `frontend/` — Next.js web UI

For production: set a strong secret key, change the default password, and follow standard security practices for your environment.

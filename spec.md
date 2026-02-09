# ARQIVE System Specification

## Overview

ARQIVE is a fully local audit-document intelligence system that combines RAG (Retrieval-Augmented Generation) with role-based access control. All components run locally on a personal laptop without requiring external APIs or cloud services.

## Architecture

```
┌─────────────────┐
│   Frontend      │
│  (Next.js/React)│
└────────┬────────┘
         │ HTTP/REST
         │
┌────────▼────────┐
│   Backend       │
│   (FastAPI)     │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼──┐  ┌────▼────┐ ┌───▼────┐
│ChromaDB│ │SQLite│  │ Ollama │ │Unstructured│
│(Vectors)│ │(Users)│  │  (LLM) │ │ (Ingestion)│
└────────┘ └──────┘  └────────┘ └──────────┘
```

## Components

### 1. Backend (Python/FastAPI)

**Location:** `backend/`

**Responsibilities:**
- User authentication via JWT
- Role-based access control (Admin, Auditor, Viewer)
- Document ingestion (PDF, DOCX, TXT)
- Text chunking and embedding generation
- Vector storage and retrieval
- RAG pipeline integration with Ollama
- REST API endpoints

**Key Modules:**

#### `auth/`
- `users.py`: User models and role definitions
- `jwt_handler.py`: JWT token creation and verification
- `roles.py`: RBAC decorators and permission checks

#### `db/`
- `vector.py`: ChromaDB wrapper for vector storage
- `sqlite.py`: SQLite operations for users and document metadata

#### `documents/`
- `ingest.py`: Document ingestion pipeline (extract, chunk, embed, store)

#### `rag/`
- `rag_engine.py`: Main RAG pipeline (retrieve + generate)
- `chunker.py`: Text chunking with token-based splitting
- `embeddings.py`: Sentence-transformers embedding generation

### 2. Frontend (Next.js/React)

**Location:** `frontend/`

**Features:**
- Login page with JWT authentication
- Chat interface for querying documents
- Document upload page
- Document list view
- Admin dashboard (role-restricted)

**Key Pages:**
- `/login`: Authentication
- `/chat`: Main query interface
- `/upload`: Document upload
- `/documents`: Document list
- `/admin`: Admin dashboard (admin only)

### 3. Data Storage

**ChromaDB:**
- Stores document chunks as vectors
- Metadata includes: document_id, filename, chunk_index, uploaded_by
- Cosine similarity search

**SQLite:**
- Users table: username, password_hash, role, email, full_name
- Documents table: id, filename, file_path, file_type, uploaded_by, metadata
- Document access table: document_id, username, access_level

## RAG Workflow

1. **Document Ingestion:**
   ```
   Upload → Extract Text → Chunk (300-500 tokens) → Generate Embeddings → Store in ChromaDB
   ```

2. **Query Processing:**
   ```
   User Query → Embed Query → Vector Search (ChromaDB) → Filter by User Access → 
   Build Context → Generate Answer (Ollama) → Return with Citations
   ```

3. **Access Control:**
   - Vector search results filtered by user permissions
   - Users can only see documents they uploaded or have explicit access to
   - Admins can access all documents

## Security Model

### Authentication
- JWT tokens with configurable expiry (default: 30 minutes)
- Tokens stored in memory (not localStorage) for security
- Password hashing using bcrypt

### Authorization
- **Admin**: Full access to all documents and user management
- **Auditor**: Can upload and query documents
- **Viewer**: Can only query documents they have access to

### Access Control
- Document-level access control
- Users can only retrieve chunks from documents they own or have access to
- Vector search includes metadata filters for user-based filtering

## API Routes

### Authentication
- `POST /auth/login` - User login (returns JWT token)

### Documents
- `POST /documents/upload` - Upload and ingest document (requires auth)
- `GET /documents/list` - List user's documents (requires auth)

### Query
- `POST /query` - RAG query endpoint (requires auth)
  - Parameters: `query` (string), `max_results` (int, default: 5)
  - Returns: `answer`, `citations`, `sources`

### Admin
- `GET /admin/users` - List all users (admin only)

### Health
- `GET /health` - Health check

## Data Schema

### Users Table
```sql
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT,
    full_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Documents Table
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_by TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (uploaded_by) REFERENCES users(username)
)
```

### Document Access Table
```sql
CREATE TABLE document_access (
    document_id TEXT NOT NULL,
    username TEXT NOT NULL,
    access_level TEXT NOT NULL,
    PRIMARY KEY (document_id, username),
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (username) REFERENCES users(username)
)
```

## Access Levels and Role Definitions

### Roles

1. **Admin** (`admin`)
   - Full system access
   - Can manage users
   - Can access all documents
   - Can view admin dashboard

2. **Auditor** (`auditor`)
   - Can upload documents
   - Can query all documents they upload
   - Can query documents shared with them
   - Cannot access admin features

3. **Viewer** (`viewer`)
   - Can query documents shared with them
   - Cannot upload documents
   - Read-only access

## Technical Stack

### Backend
- **Framework**: FastAPI
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)
- **Vector DB**: ChromaDB
- **SQL DB**: SQLite (aiosqlite)
- **Embeddings**: sentence-transformers (BAAI/bge-small-en-v1.5)
- **LLM**: Ollama (local)
- **Document Processing**: Unstructured library
- **Chunking**: tiktoken for token counting

### Frontend
- **Framework**: Next.js 14
- **Language**: TypeScript
- **HTTP Client**: Axios
- **Styling**: CSS Modules

## Local Run Instructions

### Prerequisites
1. Python 3.9+
2. Node.js 18+
3. Ollama installed and running
4. Ollama model downloaded (e.g., `ollama pull llama2`)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000`

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

### Environment Variables
Create `backend/.env`:
```
SECRET_KEY=your-secret-key-here
OLLAMA_MODEL=llama2
```

## Configuration

### Chunking
- Default chunk size: 400 tokens
- Overlap: 50 tokens
- Token counting: tiktoken (cl100k_base encoding)

### Embeddings
- Model: `BAAI/bge-small-en-v1.5`
- Dimension: 384
- Normalization: L2 normalized

### RAG
- Max context chunks: 5 (configurable)
- Similarity metric: Cosine
- Ollama base URL: `http://localhost:11434`

## Default Credentials

**⚠️ CHANGE IN PRODUCTION!**

- Username: `admin`
- Password: `admin`
- Role: `admin`

## File Structure

```
ARQIVE/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── jwt_handler.py
│   │   └── roles.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── vector.py
│   │   └── sqlite.py
│   ├── documents/
│   │   ├── __init__.py
│   │   └── ingest.py
│   └── rag/
│       ├── __init__.py
│       ├── rag_engine.py
│       ├── chunker.py
│       └── embeddings.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── src/
│       ├── pages/
│       ├── api/
│       ├── context/
│       └── styles/
├── spec.md
└── README.md
```

## Future Enhancements

- [ ] Token refresh mechanism
- [ ] Document deletion
- [ ] Advanced access control (per-document permissions)
- [ ] Document versioning
- [ ] Search history
- [ ] Export conversations
- [ ] Multi-language support
- [ ] Batch document upload
- [ ] Document preview
- [ ] Advanced chunking strategies (semantic, hierarchical)



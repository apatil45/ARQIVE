# Environment Variables Guide

Create a file named `.env` in the `backend/` directory with the following variables.

## 🔴 REQUIRED (Minimum Setup)

### SECRET_KEY
**REQUIRED for production** - Minimum 32 characters
```env
SECRET_KEY=your-secret-key-here-minimum-32-characters-long-change-this
```

**How to generate a secure key:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

---

## 🟡 RECOMMENDED (Basic Setup)

These have defaults but you should set them for your environment:

```env
# JWT Token Settings
SECRET_KEY=your-secret-key-here-minimum-32-characters-long
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Ollama Configuration (if using RAG)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Server Settings
HOST=0.0.0.0
PORT=8000

# CORS (comma-separated list)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

---

## 🟢 OPTIONAL (S3 Storage)

Only needed if you want to use S3 instead of local file storage:

```env
# Enable S3 Storage
USE_S3=false

# S3 Configuration (only if USE_S3=true)
S3_BUCKET_NAME=your-bucket-name
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=your-access-key-id
S3_SECRET_ACCESS_KEY=your-secret-access-key
```

**Note:** If `USE_S3=false` or not set, files will be stored locally in `data/uploads/`

---

## 🔵 OPTIONAL (Advanced Settings)

These have good defaults, only change if needed:

```env
# Debug Mode (shows detailed errors)
DEBUG=false

# Database Paths (defaults are fine)
SQLITE_DB_PATH=data/arqive.db
CHROMA_DB_PATH=data/chroma_db

# Embedding Model
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Chunking Settings
CHUNK_SIZE=400
CHUNK_OVERLAP=50

# Document Processing
UPLOAD_DIR=data/uploads
MAX_FILE_SIZE_MB=50

# RAG Settings
MAX_CONTEXT_CHUNKS=5
```

---

## 📝 Complete Example `.env` File

### Minimal Setup (Local Storage)
```env
# Required
SECRET_KEY=your-secret-key-here-minimum-32-characters-long-change-this

# Recommended
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Full Setup (With S3)
```env
# Required
SECRET_KEY=your-secret-key-here-minimum-32-characters-long-change-this

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# S3 Storage
USE_S3=true
S3_BUCKET_NAME=arqive-documents
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
S3_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# Debug
DEBUG=false
```

---

## ⚠️ Important Notes

1. **SECRET_KEY**: 
   - MUST be at least 32 characters
   - MUST be unique and secret
   - NEVER commit to version control
   - Generate a new one for production

2. **S3 Credentials**:
   - Can be omitted if using IAM roles (EC2, Lambda, etc.)
   - Never commit to version control
   - Use IAM users, not root credentials

3. **File Location**:
   - Create `.env` in the `backend/` directory
   - Not in the root directory
   - Not in `frontend/` directory

4. **Boolean Values**:
   - Use lowercase: `true` or `false`
   - Or: `1` or `0`
   - Or: `True` or `False`

5. **List Values (CORS_ORIGINS)**:
   - Comma-separated, no spaces: `http://localhost:3000,http://localhost:3001`
   - Or with spaces: `"http://localhost:3000, http://localhost:3001"`

---

## 🚀 Quick Start

1. Copy this template to `backend/.env`:
```bash
cd backend
# Create .env file
```

2. Minimum required content:
```env
SECRET_KEY=change-this-to-a-secure-random-string-at-least-32-characters-long
```

3. That's it! The app will work with defaults for everything else.

---

## 🔍 How to Check Your Configuration

After creating `.env`, test it:
```bash
cd backend
python -c "from config import settings; print('SECRET_KEY set:', bool(settings.SECRET_KEY and len(settings.SECRET_KEY) >= 32))"
```


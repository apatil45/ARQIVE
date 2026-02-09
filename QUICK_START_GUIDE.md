# ARQIVE Quick Start Guide - After Improvements

## 🚀 Quick Start

### 1. Update Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**New dependency**: `psutil` (optional, for health checks)

### 2. Configuration (Optional)

Create or update `backend/.env`:

```env
# Required for production
SECRET_KEY=your-secure-key-here-minimum-32-characters-long

# Optional: Performance tuning
SQLITE_USE_POOL=true
SQLITE_POOL_SIZE=5
SQLITE_MAX_OVERFLOW=10

# Optional: Logging
USE_JSON_LOGGING=false

# Optional: Security (production)
ENFORCE_SECRET_KEY=false
```

### 3. Start Backend

```bash
cd backend
python main.py
```

**What's New:**
- ✅ Request IDs in logs and responses
- ✅ Enhanced health check at `/health`
- ✅ Connection pooling (faster database operations)
- ✅ Better error messages

### 4. Start Frontend

```bash
cd frontend
npm install  # If needed
npm run dev
```

**What's New:**
- ✅ Secure token verification
- ✅ Query history support
- ✅ Document preview support

---

## 🆕 New Features

### 1. Query History

**Backend**: `GET /query/history`
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/query/history?limit=10
```

**Frontend**: Use `getQueryHistory()` from `@/api/client`

### 2. Document Preview

**Backend**: `GET /documents/{id}/preview`
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/documents/DOC_ID/preview?max_chunks=5
```

**Frontend**: Use `getDocumentPreview(documentId)` from `@/api/client`

### 3. Token Verification

**Backend**: `POST /auth/verify`
```bash
curl -X POST http://localhost:8000/auth/verify \
  -d "token=YOUR_TOKEN"
```

**Frontend**: Automatically used by `AuthContext`

---

## 🔍 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

**Returns:**
- SQLite status (with pool stats if enabled)
- ChromaDB status and document count
- Ollama connectivity and models
- Disk space (if psutil installed)
- Memory usage (if psutil installed)
- Request ID for tracing

### Logs

**Request IDs**: Every log entry now includes a request ID for tracing
**Format**: `[request_id] LEVEL logger - message`

**JSON Logging**: Set `USE_JSON_LOGGING=true` for structured logs

---

## ⚙️ Performance Tuning

### Connection Pooling

```env
SQLITE_USE_POOL=true      # Enable pooling (recommended)
SQLITE_POOL_SIZE=5        # Base pool size
SQLITE_MAX_OVERFLOW=10    # Max additional connections
```

### RAG Performance

```env
# Timeouts (seconds)
OLLAMA_TIMEOUT_GPU=30
OLLAMA_TIMEOUT_CPU=60

# Context limits (tokens)
MAX_CONTEXT_TOKENS=1500
MAX_CONTEXT_TOKENS_GPU=2000
TARGET_CONTEXT_TOKENS=500

# Cache sizes
EMBEDDING_CACHE_SIZE=1000
QUERY_RESULT_CACHE_SIZE=500
USER_DOC_CACHE_TTL=300
```

---

## 🔒 Security

### Production Checklist

1. **Set SECRET_KEY**:
   ```env
   SECRET_KEY=generate-a-secure-32-char-minimum-key
   ```

2. **Enforce SECRET_KEY**:
   ```env
   ENFORCE_SECRET_KEY=true
   ```

3. **Change default admin password**:
   - Use admin dashboard to create new admin
   - Delete default admin user

4. **Enable JSON logging** (for log aggregation):
   ```env
   USE_JSON_LOGGING=true
   ```

---

## 🐛 Troubleshooting

### Issue: "psutil not available" in health check
**Solution**: Install with `pip install psutil` or ignore (optional)

### Issue: Connection pool errors
**Solution**: Disable pooling: `SQLITE_USE_POOL=false`

### Issue: Cache not invalidating
**Solution**: Check logs for cache invalidation messages. Should happen automatically.

### Issue: Request IDs not appearing
**Solution**: Check that middleware is registered in `main.py` (should be automatic)

---

## 📊 What Changed

### Backend
- ✅ Configuration centralized
- ✅ Structured logging with request IDs
- ✅ Enhanced health checks
- ✅ Connection pooling
- ✅ Cache invalidation
- ✅ JWT verification endpoint
- ✅ Database transactions
- ✅ Query history
- ✅ Document preview

### Frontend
- ✅ Secure token verification
- ✅ API client updates for new endpoints

### Database
- ✅ New `query_history` table (auto-created)
- ✅ Connection pooling (no schema changes)

---

## ✅ Verification

After starting, verify:

1. **Health Check**:
   ```bash
   curl http://localhost:8000/health
   ```
   Should return comprehensive status with request_id

2. **Login**:
   - Login works
   - Token verification works
   - Request ID in response headers

3. **Query**:
   - Queries work
   - History is saved
   - Request ID in logs

4. **Document Upload**:
   - Upload works
   - Transaction rollback on failure
   - Cache invalidation works

---

## 📝 Migration Notes

### For Existing Deployments

1. **No breaking changes** - everything works as before
2. **New tables auto-created** - `query_history` table created on first run
3. **Optional features** - all new features are opt-in
4. **Backward compatible** - existing clients continue to work

### Database

- **No migrations needed** - new tables created automatically
- **No data loss** - all existing data preserved
- **Optional features** - query history is optional

---

## 🎯 Next Steps

1. Test the new features
2. Tune performance settings if needed
3. Enable production security settings
4. Monitor health checks
5. Review query history

---

**Status**: All improvements complete and ready for testing! ✅

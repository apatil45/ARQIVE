"""
ARQIVE Backend - FastAPI Main Entry Point
"""
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn
import json
import aiosqlite
import logging

from config import settings
from auth.jwt_handler import get_current_user, set_sqlite_db_instance
from auth.roles import require_role, Role
from auth.users import User
from documents.ingest import ingest_document
from db.vector import VectorDB
from db.sqlite import SQLiteDB
from rag.rag_engine import RAGEngine
from audit.logger import AuditLogger
from utils.logging import setup_logging, set_request_id, get_request_id

# Setup structured logging
use_json_logging = getattr(settings, 'USE_JSON_LOGGING', False)
log_level = logging.DEBUG if settings.DEBUG else logging.INFO
setup_logging(use_json=use_json_logging, level=log_level)
logger = logging.getLogger(__name__)

# Initialize databases
vector_db = VectorDB()
sqlite_db = SQLiteDB()
rag_engine = RAGEngine(vector_db, sqlite_db)  # Pass sqlite_db for efficiency

# Initialize audit logger
audit_logger = AuditLogger()

# Set global sqlite_db instance for jwt_handler
set_sqlite_db_instance(sqlite_db)

# Set global RAG engine for cache invalidation
from utils.cache_invalidation import set_rag_engine
set_rag_engine(rag_engine)


class QueryRequest(BaseModel):
    query: str
    max_results: int = 5
    stream: bool = False
    
    @classmethod
    def validate_max_results(cls, v):
        """Validate max_results is within reasonable bounds"""
        if v < 1:
            return 1
        if v > 50:  # Prevent DoS via very large queries
            return 50
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    await sqlite_db.initialize()
    await vector_db.initialize()
    yield
    # Shutdown (if needed)
    pass


app = FastAPI(title="ARQIVE API", version="1.0.0", lifespan=lifespan)

# Rate limiting setup
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled: 100 queries/hour per IP")
except ImportError:
    logger.warning("slowapi not installed. Rate limiting disabled. Install with: pip install slowapi")
    limiter = None
    RATE_LIMITING_ENABLED = False


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Don't expose internal error details in production
    error_detail = str(exc) if settings.DEBUG else "An internal error occurred"
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail, "type": type(exc).__name__}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compression middleware (reduces response size)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for tracing"""
    # Generate and set request ID
    request_id = set_request_id()
    
    # Add request ID to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    # Clear request ID after request
    from utils.logging import clear_request_id
    clear_request_id()
    
    return response

security = HTTPBearer()


@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with comprehensive system status"""
    from pathlib import Path
    
    health_status = {
        "status": "healthy",
        "service": "ARQIVE",
        "version": "1.0.0",
        "request_id": get_request_id(),
        "checks": {}
    }
    
    # Check database connectivity
    try:
        async with sqlite_db._get_connection() as db:
            await db.execute("SELECT 1")
        health_status["checks"]["sqlite"] = {
            "status": "healthy", 
            "path": sqlite_db.db_path,
            "pool_enabled": sqlite_db.use_pool
        }
        if sqlite_db.use_pool and sqlite_db._pool:
            pool_stats = await sqlite_db._pool.get_stats()
            health_status["checks"]["sqlite"]["pool_stats"] = pool_stats
    except Exception as e:
        health_status["checks"]["sqlite"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check ChromaDB
    try:
        if vector_db.collection:
            count = vector_db.collection.count()
            health_status["checks"]["chromadb"] = {
                "status": "healthy",
                "document_count": count,
                "path": settings.CHROMA_DB_PATH
            }
        else:
            health_status["checks"]["chromadb"] = {"status": "not_initialized"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["chromadb"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check Ollama connectivity
    try:
        from ollama import Client
        client = Client(host=settings.OLLAMA_BASE_URL)
        models = client.list()
        health_status["checks"]["ollama"] = {
            "status": "connected",
            "models": [m.get("name", "") for m in models.get("models", [])],
            "base_url": settings.OLLAMA_BASE_URL
        }
    except Exception as e:
        health_status["checks"]["ollama"] = {
            "status": "disconnected",
            "error": str(e),
            "base_url": settings.OLLAMA_BASE_URL
        }
        health_status["status"] = "degraded"  # Service works but RAG queries won't
    
    # Check disk space (optional, requires psutil)
    try:
        import psutil
        upload_dir = Path(settings.UPLOAD_DIR)
        if upload_dir.exists():
            disk_usage = psutil.disk_usage(upload_dir)
            health_status["checks"]["disk"] = {
                "status": "healthy",
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent_used": round(disk_usage.percent, 2)
            }
            if disk_usage.percent > 90:
                health_status["checks"]["disk"]["status"] = "warning"
                health_status["status"] = "degraded"
        else:
            health_status["checks"]["disk"] = {"status": "upload_dir_not_found"}
    except ImportError:
        health_status["checks"]["disk"] = {"status": "psutil_not_available", "note": "Install psutil for disk monitoring"}
    except Exception as e:
        health_status["checks"]["disk"] = {"status": "error", "error": str(e)}
    
    # Check memory (optional, requires psutil)
    try:
        import psutil
        memory = psutil.virtual_memory()
        health_status["checks"]["memory"] = {
            "status": "healthy",
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent_used": round(memory.percent, 2)
        }
        if memory.percent > 90:
            health_status["checks"]["memory"]["status"] = "warning"
    except ImportError:
        health_status["checks"]["memory"] = {"status": "psutil_not_available", "note": "Install psutil for memory monitoring"}
    except Exception as e:
        health_status["checks"]["memory"] = {"status": "error", "error": str(e)}
    
    return health_status


@app.post("/auth/verify")
async def verify_token_endpoint(
    request: Request,
    token: str = Form(...)
):
    """
    Verify JWT token endpoint
    Allows frontend to validate tokens without making authenticated requests
    """
    from auth.jwt_handler import verify_token_endpoint as verify_token_func
    result = await verify_token_func(token)
    return result


@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """
    User login endpoint
    Returns JWT token on successful authentication
    """
    ip_address = request.client.host if request.client else "unknown"
    
    user = await sqlite_db.get_user_by_username(username)
    if not user:
        # Log failed login attempt
        await audit_logger.log_login(
            username=username,
            ip=ip_address,
            success=False,
            failure_reason="User not found"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not await sqlite_db.verify_password(username, password):
        # Log failed login attempt
        await audit_logger.log_login(
            username=username,
            ip=ip_address,
            success=False,
            failure_reason="Invalid credentials"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    from auth.jwt_handler import create_access_token
    token = create_access_token({"sub": username, "role": user.role})
    
    # Log successful login
    await audit_logger.log_login(
        username=username,
        ip=ip_address,
        success=True
    )
    
    return {"access_token": token, "token_type": "bearer"}


@app.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and ingest a document
    Supports PDF, DOCX, TXT files
    Validates file size, type, and sanitizes filename
    """
    import os
    
    # Validate file size
    MAX_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Validate file type by magic bytes (more secure than content_type)
    detected_type = None
    
    # Check PDF magic bytes
    if file_content.startswith(b'%PDF'):
        detected_type = "application/pdf"
    # Check DOCX magic bytes (ZIP file with specific structure)
    elif file_content.startswith(b'PK\x03\x04'):
        # Check if it's a DOCX by looking for word/document.xml in first 4KB
        if b'word/document.xml' in file_content[:4096]:
            detected_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    # Check for text (UTF-8 or ASCII) - only if small enough
    elif file_size < 1024 * 1024:  # Only check text for files < 1MB
        try:
            decoded = file_content.decode('utf-8', errors='strict')
            if decoded.isprintable() or all(ord(c) < 128 for c in decoded):
                detected_type = "text/plain"
        except (UnicodeDecodeError, UnicodeError):
            pass
    
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]
    
    if detected_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Detected: {detected_type or 'unknown'}. Allowed: PDF, DOCX, TXT"
        )
    
    # Sanitize filename
    safe_filename = os.path.basename(file.filename) if file.filename else "unnamed"
    # Remove any path components and dangerous characters
    safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in "._- ")
    if not safe_filename:
        safe_filename = "document"
    
    # Update filename and content_type on the file object
    file.filename = safe_filename
    # Create a new BytesIO object for the file content
    from io import BytesIO
    file.file = BytesIO(file_content)
    file.size = file_size
    
    # Ingest document: extract, chunk, embed, and store
    # Pass detected_type separately since we can't modify UploadFile.content_type directly
    document_id = await ingest_document(file, current_user.username, vector_db, sqlite_db, detected_type)
    
    # Log document upload
    await audit_logger.log_document_upload(
        username=current_user.username,
        filename=safe_filename,
        document_id=document_id,
        file_size=file_size
    )
    
    return {"document_id": document_id, "filename": safe_filename, "status": "ingested"}


@app.get("/documents/list")
async def list_documents(
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """
    List documents accessible to the current user
    """
    # Get documents accessible to the current user
    documents = await sqlite_db.get_user_documents(current_user.username, skip, limit)
    return {"documents": documents, "count": len(documents)}


def rate_limit_query():
    """Rate limit decorator for query endpoint"""
    if RATE_LIMITING_ENABLED and limiter:
        return limiter.limit("100/hour")
    return lambda f: f  # No-op decorator if rate limiting disabled

@app.post("/query")
@rate_limit_query()
async def query_documents(
    http_request: Request,
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    RAG query endpoint
    Returns answer with citations from relevant document chunks
    Supports streaming via stream=True in request body
    Rate limited: 100 queries per hour per IP
    """
    import time
    start_time = time.time()
    ip_address = http_request.client.host if http_request.client else "unknown"
    
    if not request.query or len(request.query.strip()) == 0:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Validate and clamp max_results
    max_results = min(max(1, request.max_results), 50)
    
    try:
        # If streaming requested, use streaming endpoint
        if request.stream:
            # Note: Streaming queries are harder to audit, so we log the start
            await audit_logger.log_query(
                username=current_user.username,
                query=request.query,
                ip=ip_address,
                response_time=None,  # Streaming, can't measure total time
                success=True
            )
            return StreamingResponse(
                rag_engine.query_stream(request.query, current_user.username, max_results),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Execute RAG query with user-based filtering (non-streaming)
        # Pass user role for role-based query routing
        result = await rag_engine.query(
            request.query, 
            current_user.username, 
            max_results,
            user_role=current_user.role.value  # Pass role for audit-aware routing
        )
        
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Extract document IDs from citations for audit log
        document_ids = [c.get("document_id") for c in result.get("citations", [])]
        
        # Audit log successful query
        await audit_logger.log_query(
            username=current_user.username,
            query=request.query,
            ip=ip_address,
            document_ids=document_ids,
            response_time=response_time,
            success=True
        )
        
        # Save to query history (async, don't block response)
        try:
            answer_preview = result.get("answer", "")[:500] if result.get("answer") else None
            await sqlite_db.save_query_history(
                username=current_user.username,
                query=request.query,
                answer_preview=answer_preview,
                document_ids=document_ids,
                response_time_ms=response_time
            )
        except Exception as history_error:
            logger.warning(f"Failed to save query history: {history_error}")
            # Don't fail the request if history save fails
        
        return {
            "answer": result["answer"],
            "citations": result["citations"],
            "sources": result["sources"]
        }
    except ValueError as e:
        # Input validation errors (e.g., prompt injection detected)
        response_time = (time.time() - start_time) * 1000
        await audit_logger.log_query(
            username=current_user.username,
            query=request.query,
            ip=ip_address,
            response_time=response_time,
            success=False,
            error=str(e)
        )
        await audit_logger.log_suspicious_activity(
            username=current_user.username,
            activity_type="invalid_query",
            details={"error": str(e), "query": request.query[:200]}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other errors
        response_time = (time.time() - start_time) * 1000
        await audit_logger.log_query(
            username=current_user.username,
            query=request.query,
            ip=ip_address,
            response_time=response_time,
            success=False,
            error=str(e)
        )
        raise


@app.get("/admin/users")
async def list_users(
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """
    Admin endpoint to list all users
    """
    users = await sqlite_db.get_all_users()
    return {"users": users}


@app.get("/query/history")
async def get_query_history(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0
):
    """
    Get query history for the current user
    """
    history = await sqlite_db.get_query_history(
        username=current_user.username,
        limit=min(limit, 100),  # Cap at 100
        skip=skip
    )
    return {"history": history, "count": len(history)}


@app.delete("/query/history")
async def delete_query_history(
    current_user: User = Depends(get_current_user),
    history_id: Optional[int] = None
):
    """
    Delete query history (all or specific entry)
    """
    await sqlite_db.delete_query_history(
        username=current_user.username,
        history_id=history_id
    )
    return {"status": "deleted"}


@app.get("/documents/{document_id}/preview")
async def get_document_preview(
    document_id: str,
    current_user: User = Depends(get_current_user),
    max_chunks: int = 5
):
    """
    Get document preview (first N chunks)
    """
    # Verify user has access to document
    documents = await sqlite_db.get_user_documents(current_user.username, 0, 10000)
    doc = next((d for d in documents if d['id'] == document_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    
    # Get chunks from vector DB
    try:
        # Query with empty embedding to get chunks by document_id
        # We'll use a simple approach: get chunks by metadata filter
        filter_dict = {"document_id": document_id}
        
        # Get a dummy embedding (we just want to retrieve chunks)
        from rag.embeddings import EmbeddingModel
        embedding_model = EmbeddingModel()
        dummy_embedding = await embedding_model.embed("preview")
        
        # Query vector DB
        results = await vector_db.query(
            query_embedding=dummy_embedding,
            n_results=max_chunks,
            filter_dict=filter_dict
        )
        
        documents_list = results.get("documents", [])
        if isinstance(documents_list, list) and len(documents_list) > 0:
            if isinstance(documents_list[0], list):
                documents_list = documents_list[0]
        
        metadatas = results.get("metadatas", [])
        if isinstance(metadatas, list) and len(metadatas) > 0:
            if isinstance(metadatas[0], list):
                metadatas = metadatas[0]
        
        chunks = []
        for i, chunk_text in enumerate(documents_list[:max_chunks]):
            metadata = metadatas[i] if i < len(metadatas) else {}
            chunks.append({
                "chunk_index": metadata.get("chunk_index", i),
                "text": chunk_text,
                "filename": metadata.get("filename", doc.get("filename", ""))
            })
        
        return {
            "document_id": document_id,
            "filename": doc.get("filename", ""),
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
    except Exception as e:
        logger.error(f"Failed to get document preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get document preview: {str(e)}")


@app.post("/admin/users")
async def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    email: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """
    Admin endpoint to create a new user
    """
    from auth.users import UserCreate
    try:
        user_role = Role(role)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid role. Must be one of: {[r.value for r in Role]}"
        )
    
    user_create = UserCreate(
        username=username,
        password=password,
        role=user_role,
        email=email,
        full_name=full_name
    )
    
    try:
        new_user = await sqlite_db.create_user(user_create)
        return {"user": new_user.dict(), "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/documents/{document_id}")
async def delete_document(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document (only by owner or admin)
    """
    # Get document to check ownership
    documents = await sqlite_db.get_user_documents(current_user.username, 0, 10000)
    doc = next((d for d in documents if d['id'] == document_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user is owner or admin
    if doc['uploaded_by'] != current_user.username and current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    # Delete from vector DB, SQLite, and storage
    try:
        import json
        metadata_str = doc.get('metadata', '{}')
        metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
        chunk_count = metadata.get('chunk_count', 0)
        storage_type = metadata.get('storage_type', 'local')
        file_path = doc.get('file_path') or doc.get('file_path')  # S3 key or local path
        
        # Delete chunks from vector DB
        if chunk_count > 0:
            chunk_ids = [f"{document_id}_chunk_{i}" for i in range(chunk_count)]
            await vector_db.delete_documents(chunk_ids)
        
        # Delete file from storage (S3 or local)
        if file_path:
            if storage_type == 's3' and settings.USE_S3:
                # Delete from S3
                from storage.s3_storage import S3Storage
                storage = S3Storage()
                await storage.delete_file(file_path)
            elif storage_type == 'local' or not storage_type:
                # Delete local file
                import os
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete local file {file_path}: {e}")
        
        # Delete from SQLite
        await sqlite_db.delete_document(document_id)
        
        # Log document deletion
        await audit_logger.log_document_delete(
            username=current_user.username,
            document_id=document_id,
            filename=doc.get('filename', 'unknown')
        )
        
        return {"status": "deleted", "document_id": document_id}
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)


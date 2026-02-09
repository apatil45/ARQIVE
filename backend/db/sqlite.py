"""
SQLite database for users and document metadata
"""
import sqlite3
import aiosqlite
from typing import List, Optional, Dict
from passlib.context import CryptContext
import os
import asyncio
import logging

from config import settings
from auth.users import User, UserCreate, Role
from db.connection_pool import SQLiteConnectionPool

# Import cache invalidation (optional, to avoid circular imports)
try:
    from utils.cache_invalidation import invalidate_user_document_cache
    CACHE_INVALIDATION_AVAILABLE = True
except ImportError:
    CACHE_INVALIDATION_AVAILABLE = False
    logger.warning("Cache invalidation not available - utils.cache_invalidation not found")

logger = logging.getLogger(__name__)


class SQLiteDB:
    """SQLite database wrapper with performance optimizations and connection pooling"""
    
    def __init__(self, use_pool: Optional[bool] = None):
        """
        Initialize SQLite database wrapper
        
        Args:
            use_pool: If True, use connection pooling (recommended). If False, use direct connections (backward compatible).
                     If None, uses settings.SQLITE_USE_POOL
        """
        self.db_path = settings.SQLITE_DB_PATH
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.use_pool = use_pool if use_pool is not None else getattr(settings, 'SQLITE_USE_POOL', True)
        self._pool: Optional[SQLiteConnectionPool] = None
        
        if self.use_pool:
            pool_size = getattr(settings, 'SQLITE_POOL_SIZE', 5)
            max_overflow = getattr(settings, 'SQLITE_MAX_OVERFLOW', 10)
            self._pool = SQLiteConnectionPool(self.db_path, pool_size, max_overflow)
    
    async def _optimize_connection(self, db):
        """Apply performance optimizations to SQLite connection"""
        try:
            await db.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
            await db.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
            await db.execute('PRAGMA synchronous=NORMAL')  # Balance between safety and speed
            await db.execute('PRAGMA cache_size=10000')  # Increase cache size (10MB)
            await db.execute('PRAGMA temp_store=MEMORY')  # Store temp tables in memory
            await db.execute('PRAGMA mmap_size=268435456')  # 256MB memory-mapped I/O
            await db.commit()
        except (sqlite3.OperationalError, Exception) as e:
            # If WAL mode fails (e.g., on network drives), continue without it
            # Log but don't fail
            import warnings
            warnings.warn(f"Could not apply all SQLite optimizations: {e}", UserWarning)
    
    async def initialize(self):
        """Initialize database and create tables"""
        # Create data directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Initialize connection pool if using pooling
        if self.use_pool and self._pool:
            await self._pool.initialize()
        
        # Use connection (from pool or direct)
        async with self._get_connection() as db:
            # Apply performance optimizations (if not using pool, pool handles this)
            if not self.use_pool:
                await self._optimize_connection(db)
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Documents table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (uploaded_by) REFERENCES users(username)
                )
            """)
            
            # Document access table (for access control)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_access (
                    document_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    access_level TEXT NOT NULL,
                    PRIMARY KEY (document_id, username),
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (username) REFERENCES users(username)
                )
            """)
            
            await db.commit()
            
            # Create indexes for better query performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by 
                ON documents(uploaded_by)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at 
                ON documents(uploaded_at DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_access_document_id 
                ON document_access(document_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_access_username 
                ON document_access(username)
            """)
            
            # Query history table (for search history feature)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    query TEXT NOT NULL,
                    answer_preview TEXT,
                    document_ids TEXT,
                    response_time_ms REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (username) REFERENCES users(username)
                )
            """)
            
            # Index for query history
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_history_username 
                ON query_history(username, created_at DESC)
            """)
            
            await db.commit()
            
            # Create default admin user if no users exist
            await self._create_default_admin(db)
    
    def _get_connection(self):
        """Get database connection (from pool or create new)"""
        if self.use_pool and self._pool:
            return self._pool.acquire()
        else:
            # Backward compatible: create new connection
            return aiosqlite.connect(self.db_path)
    
    async def _create_default_admin(self, db):
        """Create default admin user if database is empty"""
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            # Default admin: admin/admin (change in production!)
            password_hash = self.pwd_context.hash("admin")
            await db.execute("""
                INSERT INTO users (username, password_hash, role, email, full_name)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", password_hash, Role.ADMIN.value, "admin@arqive.local", "System Administrator"))
            await db.commit()
    
    async def create_user(self, user_create: UserCreate) -> User:
        """Create a new user"""
        password_hash = self.pwd_context.hash(user_create.password)
        
        async with self._get_connection() as db:
            try:
                await db.execute("""
                    INSERT INTO users (username, password_hash, role, email, full_name)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_create.username,
                    password_hash,
                    user_create.role.value,
                    user_create.email,
                    user_create.full_name
                ))
                await db.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"User {user_create.username} already exists")
        
        return User(
            username=user_create.username,
            role=user_create.role,
            email=user_create.email,
            full_name=user_create.full_name
        )
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT username, role, email, full_name
                FROM users
                WHERE username = ?
            """, (username,))
            row = await cursor.fetchone()
            
            if row:
                return User(
                    username=row["username"],
                    role=Role(row["role"]),
                    email=row["email"],
                    full_name=row["full_name"]
                )
            return None
    
    async def verify_password(self, username: str, password: str) -> bool:
        """Verify user password"""
        async with self._get_connection() as db:
            cursor = await db.execute("""
                SELECT password_hash
                FROM users
                WHERE username = ?
            """, (username,))
            row = await cursor.fetchone()
            
            if row:
                return self.pwd_context.verify(password, row[0])
            return False
    
    async def get_all_users(self) -> List[User]:
        """Get all users (admin only)"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT username, role, email, full_name
                FROM users
            """)
            rows = await cursor.fetchall()
            
            return [
                User(
                    username=row["username"],
                    role=Role(row["role"]),
                    email=row["email"],
                    full_name=row["full_name"]
                )
                for row in rows
            ]
    
    async def add_document(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        file_type: str,
        uploaded_by: str,
        metadata: Optional[Dict] = None
    ):
        """Add document metadata"""
        import json
        metadata_json = json.dumps(metadata) if metadata else None
        
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO documents (id, filename, file_path, file_type, uploaded_by, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (document_id, filename, file_path, file_type, uploaded_by, metadata_json))
            await db.commit()
    
    async def delete_document(self, document_id: str):
        """Delete a document and its access records"""
        # Get list of users who had access before deletion (for cache invalidation)
        users_with_access = set()
        async with self._get_connection() as db:
            cursor = await db.execute("""
                SELECT DISTINCT username FROM document_access WHERE document_id = ?
            """, (document_id,))
            rows = await cursor.fetchall()
            users_with_access = {row[0] for row in rows}
        
        # Delete the document and access records
        async with self._get_connection() as db:
            await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            await db.execute("DELETE FROM document_access WHERE document_id = ?", (document_id,))
            await db.commit()
        
            # Invalidate cache for all users who had access
        if CACHE_INVALIDATION_AVAILABLE:
            for username in users_with_access:
                invalidate_user_document_cache(username)
                logger.debug(f"Cache invalidated for user {username} after document {document_id} deletion")
    
    async def save_query_history(
        self,
        username: str,
        query: str,
        answer_preview: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        response_time_ms: Optional[float] = None
    ):
        """Save a query to history"""
        import json
        document_ids_json = json.dumps(document_ids) if document_ids else None
        # Truncate answer preview if too long
        if answer_preview and len(answer_preview) > 500:
            answer_preview = answer_preview[:500] + "..."
        
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO query_history (username, query, answer_preview, document_ids, response_time_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (username, query[:1000], answer_preview, document_ids_json, response_time_ms))
            await db.commit()
    
    async def get_query_history(
        self,
        username: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """Get query history for a user"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, query, answer_preview, document_ids, response_time_ms, created_at
                FROM query_history
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (username, limit, skip))
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                result = dict(row)
                # Parse document_ids JSON
                if result.get("document_ids"):
                    try:
                        import json
                        result["document_ids"] = json.loads(result["document_ids"])
                    except Exception:
                        result["document_ids"] = []
                else:
                    result["document_ids"] = []
                results.append(result)
            
            return results
    
    async def delete_query_history(self, username: str, history_id: Optional[int] = None):
        """Delete query history (all or specific entry)"""
        async with self._get_connection() as db:
            if history_id:
                await db.execute("""
                    DELETE FROM query_history
                    WHERE id = ? AND username = ?
                """, (history_id, username))
            else:
                await db.execute("""
                    DELETE FROM query_history
                    WHERE username = ?
                """, (username,))
            await db.commit()
    
    async def get_user_documents(self, username: str, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get documents accessible to user (including shared documents)"""
        async with self._get_connection() as db:
            # Only optimize if not using pool (pool handles optimization)
            if not self.use_pool:
                await self._optimize_connection(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT DISTINCT d.id, d.filename, d.file_type, d.uploaded_by, d.uploaded_at, d.metadata
                FROM documents d
                LEFT JOIN document_access da ON d.id = da.document_id
                WHERE d.uploaded_by = ? OR da.username = ?
                ORDER BY d.uploaded_at DESC
                LIMIT ? OFFSET ?
            """, (username, username, limit, skip))
            rows = await cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    async def get_document_metadata(self, document_id: str) -> Optional[Dict]:
        """Get document metadata including audit metadata"""
        async with self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, filename, file_type, uploaded_by, uploaded_at, metadata
                FROM documents
                WHERE id = ?
            """, (document_id,))
            row = await cursor.fetchone()
            
            if row:
                import json
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                return {
                    "id": row["id"],
                    "filename": row["filename"],
                    "file_type": row["file_type"],
                    "uploaded_by": row["uploaded_by"],
                    "uploaded_at": row["uploaded_at"],
                    "metadata": metadata
                }
            return None
    
    async def get_user_document_ids(self, username: str) -> set:
        """Get only document IDs accessible to user (optimized for access checks)"""
        async with self._get_connection() as db:
            # Only optimize if not using pool (pool handles optimization)
            if not self.use_pool:
                await self._optimize_connection(db)
            cursor = await db.execute("""
                SELECT DISTINCT d.id
                FROM documents d
                LEFT JOIN document_access da ON d.id = da.document_id
                WHERE d.uploaded_by = ? OR da.username = ?
            """, (username, username))
            rows = await cursor.fetchall()
            
            return {row[0] for row in rows}
    
    async def get_document_access_users(self, document_id: str) -> List[Dict]:
        """Get list of users who have access to a document"""
        async with self._get_connection() as db:
            # Only optimize if not using pool (pool handles optimization)
            if not self.use_pool:
                await self._optimize_connection(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT username, access_level
                FROM document_access
                WHERE document_id = ?
            """, (document_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def grant_document_access(
        self, 
        document_id: str, 
        username: str, 
        access_level: str = "read"
    ):
        """Grant access to a document for a user"""
        async with self._get_connection() as db:
            # Only optimize if not using pool (pool handles optimization)
            if not self.use_pool:
                await self._optimize_connection(db)
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO document_access (document_id, username, access_level)
                    VALUES (?, ?, ?)
                """, (document_id, username, access_level))
                await db.commit()
                
                # Invalidate cache for the user who was granted access
                if CACHE_INVALIDATION_AVAILABLE:
                    invalidate_user_document_cache(username)
                    logger.debug(f"Cache invalidated for user {username} after granting access to document {document_id}")
            except sqlite3.IntegrityError:
                raise ValueError(f"Invalid document_id or username")
    
    async def revoke_document_access(self, document_id: str, username: str):
        """Revoke access to a document for a user"""
        async with self._get_connection() as db:
            # Only optimize if not using pool (pool handles optimization)
            if not self.use_pool:
                await self._optimize_connection(db)
            await db.execute("""
                DELETE FROM document_access
                WHERE document_id = ? AND username = ?
            """, (document_id, username))
            await db.commit()
            
            # Invalidate cache for the user who lost access
            if CACHE_INVALIDATION_AVAILABLE:
                invalidate_user_document_cache(username)
                logger.debug(f"Cache invalidated for user {username} after revoking access to document {document_id}")


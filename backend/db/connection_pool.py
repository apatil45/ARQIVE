"""
SQLite connection pool for efficient connection reuse
Thread-safe and async-compatible
"""
import aiosqlite
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
import logging
from config import settings

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """
    Connection pool for SQLite database connections
    Reuses connections efficiently while maintaining thread safety
    """
    
    def __init__(self, db_path: str, pool_size: int = 5, max_overflow: int = 10):
        """
        Initialize connection pool
        
        Args:
            db_path: Path to SQLite database file
            pool_size: Number of connections to keep in pool
            max_overflow: Maximum additional connections beyond pool_size
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self._created_connections = 0
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize pool with optimized connections"""
        if self._initialized:
            return
        
        # Pre-create some connections
        for _ in range(min(2, self.pool_size)):  # Start with 2 connections
            conn = await self._create_connection()
            await self._pool.put(conn)
            self._created_connections += 1
        
        self._initialized = True
        logger.info(f"SQLite connection pool initialized with {self._created_connections} connections")
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new optimized connection"""
        conn = await aiosqlite.connect(self.db_path)
        
        # Apply optimizations
        await conn.execute('PRAGMA foreign_keys = ON')
        try:
            await conn.execute('PRAGMA journal_mode=WAL')
        except Exception:
            pass  # WAL may not work on network drives
        
        await conn.execute('PRAGMA synchronous=NORMAL')
        await conn.execute('PRAGMA cache_size=10000')
        await conn.execute('PRAGMA temp_store=MEMORY')
        await conn.execute('PRAGMA mmap_size=268435456')
        await conn.commit()
        
        return conn
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool
        
        Usage:
            async with pool.acquire() as conn:
                await conn.execute(...)
        """
        conn = None
        try:
            # Try to get from pool (non-blocking)
            try:
                conn = self._pool.get_nowait()
            except asyncio.QueueEmpty:
                # Pool is empty, check if we can create more
                async with self._lock:
                    if self._created_connections < self.pool_size + self.max_overflow:
                        conn = await self._create_connection()
                        self._created_connections += 1
                        logger.debug(f"Created new connection (total: {self._created_connections})")
                    else:
                        # Wait for a connection to become available
                        conn = await self._pool.get()
            
            yield conn
            
        finally:
            # Return connection to pool
            if conn:
                try:
                    # Check if connection is still valid
                    await conn.execute("SELECT 1")
                    # Return to pool if pool not full
                    try:
                        self._pool.put_nowait(conn)
                    except asyncio.QueueFull:
                        # Pool is full, close this connection
                        await conn.close()
                        async with self._lock:
                            self._created_connections -= 1
                        logger.debug("Pool full, closed connection")
                except Exception as e:
                    # Connection is invalid, don't return to pool
                    logger.warning(f"Connection invalid, not returning to pool: {e}")
                    try:
                        await conn.close()
                    except Exception:
                        pass
                    async with self._lock:
                        self._created_connections -= 1
    
    async def close_all(self):
        """Close all connections in pool"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                await conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
        
        async with self._lock:
            self._created_connections = 0
            self._initialized = False
        
        logger.info("All connections in pool closed")
    
    async def get_stats(self) -> dict:
        """Get pool statistics"""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "created_connections": self._created_connections,
            "available_connections": self._pool.qsize(),
            "initialized": self._initialized
        }

"""
Transaction utilities for ensuring data consistency across multiple databases
"""
import logging
from typing import Optional, Callable, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages transactions across multiple data stores (SQLite, ChromaDB)
    Implements a two-phase commit pattern for consistency
    """
    
    def __init__(self):
        self._operations: list = []
        self._rollback_operations: list = []
    
    def add_operation(
        self,
        operation: Callable,
        rollback: Optional[Callable] = None,
        description: str = ""
    ):
        """
        Add an operation to the transaction
        
        Args:
            operation: Async function to execute
            rollback: Async function to rollback this operation
            description: Human-readable description
        """
        self._operations.append({
            "operation": operation,
            "rollback": rollback,
            "description": description
        })
    
    async def execute(self) -> Any:
        """
        Execute all operations in the transaction
        Returns the result of the last operation
        
        If any operation fails, all previous operations are rolled back
        """
        executed_operations = []
        last_result = None
        
        try:
            for i, op in enumerate(self._operations):
                logger.debug(f"Executing transaction operation {i+1}/{len(self._operations)}: {op['description']}")
                result = await op["operation"]()
                executed_operations.append(i)
                last_result = result
            
            logger.info(f"Transaction completed successfully: {len(executed_operations)} operations")
            return last_result
            
        except Exception as e:
            logger.error(f"Transaction failed at operation {len(executed_operations)}: {e}")
            logger.info(f"Rolling back {len(executed_operations)} operations...")
            
            # Rollback in reverse order
            for i in reversed(executed_operations):
                op = self._operations[i]
                if op["rollback"]:
                    try:
                        await op["rollback"]()
                        logger.debug(f"Rolled back operation {i+1}: {op['description']}")
                    except Exception as rollback_error:
                        logger.error(f"Rollback failed for operation {i+1}: {rollback_error}", exc_info=True)
            
            raise
    
    def clear(self):
        """Clear all operations"""
        self._operations.clear()
        self._rollback_operations.clear()


@asynccontextmanager
async def document_ingestion_transaction(
    vector_db,
    sqlite_db,
    document_id: str,
    chunk_ids: list,
    file_storage_path: Optional[str] = None
):
    """
    Context manager for document ingestion transaction
    
    Ensures that if ingestion fails, all data is cleaned up:
    - Vector DB chunks are deleted
    - SQLite document record is deleted
    - Uploaded file is deleted
    
    Usage:
        async with document_ingestion_transaction(...) as tx:
            # Perform operations
            await vector_db.add_documents(...)
            await sqlite_db.add_document(...)
    """
    import os
    from config import settings
    
    tx = TransactionManager()
    cleanup_complete = False
    
    try:
        yield tx
        
        # If we get here, all operations succeeded
        cleanup_complete = True
        
    except Exception as e:
        logger.error(f"Document ingestion transaction failed: {e}", exc_info=True)
        
        # Cleanup: Delete chunks from vector DB
        if chunk_ids:
            try:
                await vector_db.delete_documents(chunk_ids)
                logger.info(f"Cleaned up {len(chunk_ids)} chunks from vector DB")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup vector DB chunks: {cleanup_error}")
        
        # Cleanup: Delete document from SQLite
        try:
            await sqlite_db.delete_document(document_id)
            logger.info(f"Cleaned up document {document_id} from SQLite")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup SQLite document: {cleanup_error}")
        
        # Cleanup: Delete uploaded file
        if file_storage_path:
            try:
                if settings.USE_S3 and settings.S3_BUCKET_NAME:
                    # Delete from S3
                    from storage.s3_storage import S3Storage
                    storage = S3Storage()
                    await storage.delete_file(file_storage_path)
                    logger.info(f"Cleaned up S3 file: {file_storage_path}")
                elif os.path.exists(file_storage_path):
                    # Delete local file
                    os.remove(file_storage_path)
                    logger.info(f"Cleaned up local file: {file_storage_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup file {file_storage_path}: {cleanup_error}")
        
        # Re-raise the original exception
        raise

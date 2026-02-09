"""
Audit logging for security and compliance
"""
import json
import aiofiles
from datetime import datetime
from typing import Optional, List, Dict
import os
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs all security-relevant events for compliance and security monitoring"""
    
    def __init__(self):
        self.log_dir = "data/audit_logs"
        os.makedirs(self.log_dir, exist_ok=True)
        logger.info(f"Audit logging initialized. Logs directory: {self.log_dir}")
    
    async def log_query(self, username: str, query: str, ip: str, 
                       document_ids: Optional[List[str]] = None,
                       response_time: Optional[float] = None,
                       success: bool = True,
                       error: Optional[str] = None):
        """Log a query event"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "query",
            "username": username,
            "ip_address": ip,
            "query": query[:500],  # Limit length for security
            "document_ids_accessed": document_ids or [],
            "response_time_ms": response_time,
            "success": success,
            "error": error
        }
        
        await self._write_log(log_entry)
    
    async def log_login(self, username: str, ip: str, success: bool, 
                       failure_reason: Optional[str] = None):
        """Log a login event"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "login",
            "username": username,
            "ip_address": ip,
            "success": success,
            "failure_reason": failure_reason
        }
        
        await self._write_log(log_entry)
        
        # Log failed login attempts to separate file for security monitoring
        if not success:
            await self._write_log(log_entry, filename="failed_logins.log")
    
    async def log_document_upload(self, username: str, filename: str, 
                                  document_id: str, file_size: int):
        """Log a document upload"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "document_upload",
            "username": username,
            "filename": filename,
            "document_id": document_id,
            "file_size_bytes": file_size,
        }
        
        await self._write_log(log_entry)
    
    async def log_document_delete(self, username: str, document_id: str, 
                                  filename: str):
        """Log a document deletion"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "document_delete",
            "username": username,
            "document_id": document_id,
            "filename": filename,
        }
        
        await self._write_log(log_entry)
    
    async def log_suspicious_activity(self, username: str, activity_type: str, 
                                     details: Dict):
        """Log suspicious activity for security monitoring"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "suspicious_activity",
            "username": username,
            "activity_type": activity_type,
            "details": details,
        }
        
        await self._write_log(log_entry)
        # Also log to separate suspicious file for easy monitoring
        await self._write_log(log_entry, filename="suspicious.log")
        logger.warning(f"Suspicious activity detected: {activity_type} by {username}")
    
    async def _write_log(self, entry: Dict, filename: str = "audit.log"):
        """Write log entry to file (async)"""
        log_file = os.path.join(self.log_dir, filename)
        try:
            async with aiofiles.open(log_file, 'a') as f:
                await f.write(json.dumps(entry) + '\n')
        except Exception as e:
            # Don't fail the request if logging fails, but log the error
            logger.error(f"Failed to write audit log to {log_file}: {e}")


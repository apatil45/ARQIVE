"""
Structured logging utilities with request ID tracking
"""
import logging
import uuid
from contextvars import ContextVar
from typing import Optional
import json
from datetime import datetime

# Context variable for request ID (thread-safe)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Get request ID from context
        request_id = request_id_var.get()
        
        # Build structured log entry
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request ID if available
        if request_id:
            log_data["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Return JSON string or formatted string based on settings
        if getattr(record, 'use_json', False):
            return json.dumps(log_data)
        else:
            # Human-readable format with request ID
            request_id_str = f"[{request_id}] " if request_id else ""
            return f"{log_data['timestamp']} {log_data['level']:8s} {request_id_str}{log_data['logger']} - {log_data['message']}"


def get_request_id() -> Optional[str]:
    """Get current request ID from context"""
    return request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set request ID in context, generate new one if not provided"""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def clear_request_id():
    """Clear request ID from context"""
    request_id_var.set(None)


def setup_logging(use_json: bool = False, level: int = logging.INFO):
    """
    Setup structured logging
    
    Args:
        use_json: If True, output JSON format. If False, human-readable format
        level: Logging level
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Set formatter
    formatter = StructuredFormatter()
    console_handler.setFormatter(formatter)
    
    # Add handler
    root_logger.addHandler(console_handler)
    
    # Store use_json in formatter for later use
    console_handler.formatter.use_json = use_json

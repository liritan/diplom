"""
Structured logging configuration for the application.

Provides JSON-formatted logging for better monitoring and analysis.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in JSON format for structured logging.
    
    This makes it easier to parse logs in monitoring systems like ELK, Splunk, etc.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            str: JSON-formatted log entry
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add custom fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "extra_fields"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False)


class LLMCallLogger:
    """
    Logger specifically for LLM API calls.
    
    Tracks prompts, responses, timing, and errors for monitoring and debugging.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize LLM call logger.
        
        Args:
            logger: Base logger to use
        """
        self.logger = logger
    
    def log_request(
        self,
        request_id: str,
        method: str,
        prompt: str,
        context: Dict[str, Any] = None
    ) -> None:
        """
        Log an LLM API request.
        
        Args:
            request_id: Unique identifier for this request
            method: Method being called (e.g., 'analyze_communication')
            prompt: The prompt being sent to LLM
            context: Additional context information
        """
        log_data = {
            "event": "llm_request",
            "request_id": request_id,
            "method": method,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
        }
        
        if context:
            log_data["context"] = context
        
        # Create a log record with extra fields
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(logging_config.py)",
            0,
            "LLM API request",
            (),
            None
        )
        record.extra_fields = log_data
        self.logger.handle(record)
    
    def log_response(
        self,
        request_id: str,
        method: str,
        response: str,
        duration_ms: float,
        success: bool = True
    ) -> None:
        """
        Log an LLM API response.
        
        Args:
            request_id: Unique identifier for this request
            method: Method that was called
            response: The response from LLM
            duration_ms: Time taken in milliseconds
            success: Whether the request was successful
        """
        log_data = {
            "event": "llm_response",
            "request_id": request_id,
            "method": method,
            "response_length": len(response),
            "response_preview": response[:200] + "..." if len(response) > 200 else response,
            "duration_ms": duration_ms,
            "success": success,
        }
        
        # Create a log record with extra fields
        level = logging.INFO if success else logging.ERROR
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(logging_config.py)",
            0,
            "LLM API response",
            (),
            None
        )
        record.extra_fields = log_data
        self.logger.handle(record)
    
    def log_error(
        self,
        request_id: str,
        method: str,
        error: Exception,
        duration_ms: float
    ) -> None:
        """
        Log an LLM API error.
        
        Args:
            request_id: Unique identifier for this request
            method: Method that was called
            error: The exception that occurred
            duration_ms: Time taken before error
        """
        log_data = {
            "event": "llm_error",
            "request_id": request_id,
            "method": method,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "duration_ms": duration_ms,
        }
        
        # Create a log record with extra fields
        record = self.logger.makeRecord(
            self.logger.name,
            logging.ERROR,
            "(logging_config.py)",
            0,
            f"LLM API error: {str(error)}",
            (),
            None
        )
        record.extra_fields = log_data
        self.logger.handle(record)


def setup_logging(
    log_level: str = "INFO",
    use_json: bool = True
) -> None:
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON formatting (default: True)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Set formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    root_logger.info(f"Logging configured: level={log_level}, json_format={use_json}")


# Create a global LLM call logger instance
llm_call_logger = LLMCallLogger(logging.getLogger("app.services.llm"))

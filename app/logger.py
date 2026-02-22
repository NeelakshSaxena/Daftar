import os
import json
import logging
import datetime
import contextvars
import sys
from logging.handlers import TimedRotatingFileHandler

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Point to Daftar/data/logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }
        
        # Handle message which can be a dict (structured data) or string
        if isinstance(record.msg, dict):
            log_record.update(record.msg)
        else:
            log_record["message"] = record.getMessage()
            
        req_id = request_id_var.get()
        if req_id:
            log_record["request_id"] = req_id
            
        # Add kwargs if logged with `extra={}`
        if hasattr(record, "session_id"):
            log_record["session_id"] = record.session_id
        if hasattr(record, "event_type"):
            log_record["event_type"] = record.event_type
            
        # Include exception traceback if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_logger(name: str, log_file: str, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times if logger is already configured
    if not logger.handlers:
        file_path = os.path.join(LOGS_DIR, log_file)
        handler = TimedRotatingFileHandler(
            file_path, 
            when="midnight", 
            interval=1, 
            backupCount=30, 
            encoding="utf-8"
        )
        handler.suffix = "%Y-%m-%d"
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    return logger

# Initialize standard loggers
system_logger = setup_logger("system", "system.log")
chat_logger = setup_logger("chat", "chat.log")
tool_logger = setup_logger("tools", "tools.log")
memory_logger = setup_logger("memory", "memory.log")
settings_logger = setup_logger("settings", "settings.log")

def redact_token(token: str) -> str | None:
    if not token:
        return None
    token = token.strip()
    return token[:6] + "..." if len(token) > 6 else "***"

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    system_logger.error(
        {
            "event_type": "uncaught_exception", 
            "status": "failure", 
            "error_type": exc_type.__name__, 
            "error_message": str(exc_value)
        },
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = handle_exception

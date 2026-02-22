import os
import json
import logging
import datetime
from logging.handlers import TimedRotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
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

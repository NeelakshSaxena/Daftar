import json
import os
from app.logger import system_logger

_default_config = os.path.join(os.path.dirname(__file__), "config", "defaults.json")
CONFIG_PATH = os.environ.get("DAFTAR_CONFIG_PATH", _default_config)
# Static setting, not dynamically configurable via DB yet
MAX_CHAT_HISTORY = 20

def coerce_value(key, value):
    if key == "memory_extraction_threshold":
        return float(value)
    return value

def load_settings(db=None):
    settings = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    settings = loaded
        except Exception as e:
            system_logger.error({"event_type": "load_defaults_failed", "error": str(e)}, exc_info=True)
            
    try:
        if db is None:
            from memory.db import MemoryDB
            db = MemoryDB(init_db=False)
        overrides = db.get_all_overrides()
        for k, v in overrides.items():
            try:
                settings[k] = coerce_value(k, v)
            except Exception as e:
                system_logger.error({"event_type": "coerce_override_failed", "key": k, "value": v, "error": str(e)}, exc_info=True)
    except Exception as e:
        system_logger.error({"event_type": "load_overrides_failed", "error": str(e)}, exc_info=True)
        
    return settings


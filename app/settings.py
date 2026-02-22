import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "defaults.json")
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
            print(f"Error loading defaults.json: {e}")
            
    try:
        if db is None:
            from memory.db import MemoryDB
            db = MemoryDB(init_db=False)
        overrides = db.get_all_overrides()
        for k, v in overrides.items():
            try:
                settings[k] = coerce_value(k, v)
            except Exception as e:
                print(f"Error coercing override for {k} with value {v}: {e}. Falling back to default.")
    except Exception as e:
        print(f"Error loading settings overrides from DB: {e}")
        
    return settings


import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "defaults.json")
MAX_CHAT_HISTORY = 20

def load_settings():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

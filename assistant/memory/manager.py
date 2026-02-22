import os
import json
from settings import MAX_CHAT_HISTORY

MEMORY_DIR = os.path.dirname(__file__)

class MemoryManager:
    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        
    def _sanitize_session_id(self, session_id: str) -> str:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return safe_id if safe_id else "default"

    def _get_file_path(self, session_id: str) -> str:
        safe_session_id = self._sanitize_session_id(session_id)
        return os.path.join(MEMORY_DIR, f"history_{safe_session_id}.json")
        
    def load(self, session_id: str) -> list:
        file_path = self._get_file_path(session_id)
        
        if not os.path.exists(file_path):
            return []
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                messages = json.loads(content)
                if not isinstance(messages, list):
                    return []
                
                # Filter out system messages just in case they slipped in
                return [m for m in messages if m.get("role") in ("user", "assistant")]
        except json.JSONDecodeError:
            # Corrupt file, backup and start fresh
            safe_session_id = self._sanitize_session_id(session_id)
            corrupted_path = os.path.join(MEMORY_DIR, f"history_{safe_session_id}.corrupted.json")
            try:
                os.replace(file_path, corrupted_path)
            except Exception:
                pass
            return []
        except Exception:
            return []

    def save(self, session_id: str, messages: list) -> None:
        # We assume messages are already pruned and contain no system prompts
        # but let's be double safe
        safe_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
        
        file_path = self._get_file_path(session_id)
        tmp_path = file_path + ".tmp"
        
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(safe_messages, f, indent=2, ensure_ascii=False)
                
            os.replace(tmp_path, file_path)
        except Exception as e:
            # Let it fail gracefully or log it in real scenario
            print(f"Error saving history for session {session_id}: {e}")

    def prune(self, messages: list, reserve: int = 0) -> list:
        """
        Prunes the history to MAX_CHAT_HISTORY - reserve.
        Only keeps the last N items.
        """
        max_allowed = max(0, MAX_CHAT_HISTORY - reserve)
        if len(messages) > max_allowed:
            # Keep the last max_allowed messages
            return messages[-max_allowed:]
        return messages

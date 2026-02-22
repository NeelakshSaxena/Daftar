import os
import sqlite3
from typing import List, Optional
from datetime import datetime

MEMORY_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(MEMORY_DIR, "memory.db")

class MemoryDB:
    def __init__(self, init_db: bool = True):
        if init_db:
            self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if not columns:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL DEFAULT 'default_user',
                        memory_date TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        importance INTEGER NOT NULL,
                        access_mode TEXT NOT NULL DEFAULT 'private',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                        UNIQUE(memory_id, version)
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings_overrides (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memory_versions_lookup 
                    ON memory_versions(memory_id, version DESC)
                """)

            elif "content" in columns:
                print("Migrating memories to versioned schema (v3)...")
                cursor.execute("ALTER TABLE memories RENAME TO old_memories")
                today = datetime.now().strftime("%Y-%m-%d")
                
                cursor.execute("""
                    CREATE TABLE memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL DEFAULT 'default_user',
                        memory_date TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        importance INTEGER NOT NULL,
                        access_mode TEXT NOT NULL DEFAULT 'private',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE memory_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                        UNIQUE(memory_id, version)
                    )
                """)
                
                cursor.execute(f"""
                    INSERT INTO memories (id, session_id, user_id, memory_date, subject, importance, access_mode, created_at)
                    SELECT id, session_id, 'default_user', '{today}', 'Legacy', 3, 'private', timestamp FROM old_memories
                """)
                
                cursor.execute("""
                    INSERT INTO memory_versions (memory_id, content, version, timestamp)
                    SELECT id, content, 1, timestamp FROM old_memories
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memory_versions_lookup 
                    ON memory_versions(memory_id, version DESC)
                """)
                
                cursor.execute("DROP TABLE old_memories")
                
            elif "memory_date" not in columns:
                print("Migrating memories to v3 schema (adding date, subject, importance)...")
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute(f"ALTER TABLE memories ADD COLUMN memory_date TEXT NOT NULL DEFAULT '{today}'")
                cursor.execute("ALTER TABLE memories ADD COLUMN subject TEXT NOT NULL DEFAULT 'Legacy'")
                cursor.execute("ALTER TABLE memories ADD COLUMN importance INTEGER NOT NULL DEFAULT 3")

            # Post schema migration checks for v4
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            if columns and "user_id" not in columns:
                print("Migrating memories to v4 schema (adding user_id, access_mode)...")
                cursor.execute("ALTER TABLE memories ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")
                cursor.execute("ALTER TABLE memories ADD COLUMN access_mode TEXT NOT NULL DEFAULT 'private'")

            # Check if settings_overrides exists individually to handle migrations robustly
            cursor.execute("PRAGMA table_info(settings_overrides)")
            if not cursor.fetchall():
                cursor.execute("""
                    CREATE TABLE settings_overrides (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            conn.commit()

    def _build_access_filter(self, user_id: str, allowed_subjects: Optional[List[str]] = None) -> tuple[str, list]:
        """
        Builds the standard WHERE clause conditions for memory access control.
        Returns a tuple of (sql_clause_string, params_list).
        """
        if allowed_subjects is None:
            allowed_subjects = ["*"]
            
        allow_all = '*' in allowed_subjects
        placeholders = ','.join('?' * len(allowed_subjects)) or "''"
        
        clause = f"AND (m.user_id = ? OR m.access_mode = 'shared') AND (? OR m.subject IN ({placeholders}))"
        params = [user_id, allow_all] + allowed_subjects
        
        return clause, params

    def store_memory(self, session_id: str, content: str, memory_date: str, subject: str, importance: int, user_id: str = "default_user", access_mode: str = "private") -> Optional[int]:
        """
        Stores a memory if it doesn't already exist for this session.
        Returns the new memory_id if inserted, None if duplicate or error.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check for duplicates across all active versions for this session and user
                cursor.execute("""
                    SELECT 1 FROM memory_versions mv
                    JOIN memories m ON m.id = mv.memory_id
                    WHERE m.session_id = ? AND m.user_id = ? AND mv.content = ?
                """, (session_id, user_id, content))
                
                if cursor.fetchone():
                    return None
                
                cursor.execute(
                    "INSERT INTO memories (session_id, user_id, memory_date, subject, importance, access_mode) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, user_id, memory_date, subject, importance, access_mode)
                )
                memory_id = cursor.lastrowid
                
                cursor.execute(
                    "INSERT INTO memory_versions (memory_id, content, version) VALUES (?, ?, ?)",
                    (memory_id, content, 1)
                )
                conn.commit()
                return memory_id
        except Exception as e:
            print(f"Error storing memory: {e}")
            return None

    def edit_memory(self, memory_id: int, new_content: str, session_id: Optional[str] = None) -> bool:
        """
        Edits a memory by appending a new version with incremented version number.
        Retrieves current max version from DB for safety.
        Returns True on success, False if validation fails or memory not found.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if memory exists and validate session_id
                cursor.execute("SELECT session_id FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                if session_id and row[0] != session_id:
                    return False
                    
                # Find current max version
                cursor.execute("SELECT MAX(version) FROM memory_versions WHERE memory_id = ?", (memory_id,))
                v_row = cursor.fetchone()
                current_version = v_row[0] if v_row and v_row[0] else 0
                new_version = current_version + 1
                
                cursor.execute(
                    "INSERT INTO memory_versions (memory_id, content, version) VALUES (?, ?, ?)",
                    (memory_id, new_content, new_version)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error editing memory: {e}")
            return False

    def retrieve_recent_memories(self, session_id: str, user_id: str = "default_user", allowed_subjects: Optional[List[str]] = None, limit: int = 5) -> List[str]:
        """
        Retrieves the most recent memories for a given session.
        Fetches only the latest version of each memory efficiently via SQL.
        Filters based on user ownership and allowed subjects.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                access_clause, access_params = self._build_access_filter(user_id, allowed_subjects)

                query = f"""
                    SELECT mv.content
                    FROM memory_versions mv
                    JOIN (
                        SELECT memory_id, MAX(version) as max_version
                        FROM memory_versions
                        GROUP BY memory_id
                    ) latest ON mv.memory_id = latest.memory_id AND mv.version = latest.max_version
                    JOIN memories m ON m.id = mv.memory_id
                    WHERE m.session_id = ? 
                      {access_clause}
                    ORDER BY m.created_at DESC
                    LIMIT ?
                """
                params = [session_id] + access_params + [limit]
                
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []

    def get_daily_aggregation(self, session_id: str, memory_date: str, user_id: str = "default_user", allowed_subjects: Optional[List[str]] = None, min_importance: int = 3) -> dict:
        """
        Returns a dict mapping subject to a list of memory dicts (content, importance).
        { 'Work': [{'content': '...', 'importance': 4}], ... }
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                access_clause, access_params = self._build_access_filter(user_id, allowed_subjects)

                query = f"""
                    SELECT m.subject, m.importance, mv.content
                    FROM memory_versions mv
                    JOIN (
                        SELECT memory_id, MAX(version) as max_version
                        FROM memory_versions
                        GROUP BY memory_id
                    ) latest ON mv.memory_id = latest.memory_id AND mv.version = latest.max_version
                    JOIN memories m ON m.id = mv.memory_id
                    WHERE m.session_id = ? 
                      AND m.memory_date = ? 
                      AND m.importance >= ?
                      {access_clause}
                    ORDER BY m.importance DESC, m.created_at DESC
                """
                params = [session_id, memory_date, min_importance] + access_params
                
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                result = {}
                for subject, importance, content in rows:
                    if subject not in result:
                        result[subject] = []
                    result[subject].append({
                        "content": content,
                        "importance": importance
                    })
                return result
        except Exception as e:
            print(f"Error retrieving daily aggregation: {e}")
            return {}

    def get_all_overrides(self) -> dict:
        """
        Retrieves all key-value overrides from the database.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM settings_overrides")
                rows = cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception as e:
            print(f"Error retrieving settings overrides: {e}")
            return {}

    def set_setting_override(self, key: str, value: str) -> bool:
        """
        Upserts a setting override in the database.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO settings_overrides (key, value, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET 
                        value=excluded.value, 
                        updated_at=CURRENT_TIMESTAMP
                """, (key, str(value)))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error setting override for {key}: {e}")
            return False


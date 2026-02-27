import os
import sqlite3
from typing import List, Optional
from datetime import datetime
from app.logger import memory_logger

_default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "database")
DB_DIR = os.environ.get("DAFTAR_DB_DIR", _default_dir)
DB_PATH = os.path.join(DB_DIR, "memory.db")

class MemoryDB:
    def __init__(self, init_db: bool = True):
        if init_db:
            self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        # Infrastructure Hardening: WAL mode allows concurrent readers while writing
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    def _init_db(self):
        os.makedirs(DB_DIR, exist_ok=True)
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

            # Post schema migration checks for v5 (Lifecycle & Policy Engine)
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            if columns and "state" not in columns:
                print("Migrating memories to v5 schema (adding lifecycle states)...")
                cursor.execute("ALTER TABLE memories ADD COLUMN state TEXT NOT NULL DEFAULT 'active'")
                cursor.execute("ALTER TABLE memories ADD COLUMN supersedes_memory_id INTEGER NULL")
                cursor.execute("ALTER TABLE memories ADD COLUMN confidence_score REAL NOT NULL DEFAULT 1.0")
                cursor.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'inferred'")

            # Post schema migration checks for L7 (Concurrency)
            if columns and "content_hash" not in columns:
                print("Migrating memories to L7 schema (adding content_hash for deterministic locking)...")
                cursor.execute("ALTER TABLE memories ADD COLUMN content_hash TEXT NOT NULL DEFAULT 'legacy_hash'")
                
            # Update existing records to avoid immediate UNIQUE constraint failure from partial migrations
            cursor.execute("UPDATE memories SET content_hash = hex(randomblob(16)) WHERE content_hash = 'legacy_hash'")
            
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

            # Enforce unique active content_hash per user to stop race condition flood inserts
            # Ensure no existing duplicates block the index creation (could happen from interrupted testing)
            cursor.execute("""
                UPDATE memories SET content_hash = hex(randomblob(16)) 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM memories 
                    WHERE state = 'active'
                    GROUP BY user_id, content_hash
                ) AND state = 'active'
            """)
            
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_active_memories_hash 
                ON memories(user_id, content_hash) WHERE state = 'active'
            """)
            
            # Rate Limiting table for governance
            cursor.execute("PRAGMA table_info(rate_limits)")
            if not cursor.fetchall():
                cursor.execute("""
                    CREATE TABLE rate_limits (
                        user_id TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        window_start INTEGER NOT NULL,
                        request_count INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY (user_id, endpoint, window_start)
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

    def insert_memory(self, session_id: str, content: str, memory_date: str, subject: str, importance: int, 
                      user_id: str = "default_user", access_mode: str = "private",
                      state: str = "active", supersedes_memory_id: Optional[int] = None, 
                      confidence_score: float = 1.0, source: str = "inferred",
                      correlation_id: str = "none") -> Optional[int]:
        """
        Inserts a new memory into the DB strictly (append-only).
        Returns the new memory_id if inserted, None if error.
        """
        import time
        import hashlib
        
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        start_time = time.time()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO memories (session_id, user_id, memory_date, subject, importance, access_mode, state, supersedes_memory_id, confidence_score, source, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, user_id, memory_date, subject, importance, access_mode, state, supersedes_memory_id, confidence_score, source, content_hash)
                )
                memory_id = cursor.lastrowid
                
                cursor.execute(
                    "INSERT INTO memory_versions (memory_id, content, version) VALUES (?, ?, ?)",
                    (memory_id, content, 1)
                )
                conn.commit()
                
                memory_logger.info({
                    "event_type": "state_mutation_committed",
                    "status": "success",
                    "memory_id": memory_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "subject": subject,
                    "state": state,
                    "correlation_id": correlation_id,
                    "content_hash": content_hash[:8],
                    "duration_ms": int((time.time() - start_time) * 1000)
                })
                
                return memory_id
        except sqlite3.IntegrityError as e:
            # Hash uniqueness constraint caught a concurrent flood insertion
            if "UNIQUE constraint failed" in str(e):
                return -1 # -1 denotes DUPLICATE constraint triggered natively
            else:
                return None
        except Exception as e:
            memory_logger.error({
                "event_type": "state_mutation_failed",
                "status": "failure",
                "correlation_id": correlation_id,
                "session_id": session_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            return None

    def set_memory_state(self, memory_id: int, new_state: str) -> bool:
        """
        Updates the lifecycle state of a memory safely.
        Returns True ONLY if the update actually mutated a row (OCC check).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE memories SET state = ? WHERE id = ? AND state != ?", (new_state, memory_id, new_state))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            memory_logger.error({"event_type": "update_state_failed", "memory_id": memory_id, "error": str(e)}, exc_info=True)
            return False

    def get_active_memories_by_subject(self, session_id: str, user_id: str, subject: str) -> List[dict]:
        """
        Retrieves all 'active' memories for a specific session/user/subject for Policy Engine evaluation.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT m.id, mv.content, m.confidence_score, m.source, m.importance
                    FROM memories m
                    JOIN (
                        SELECT memory_id, MAX(version) as max_version
                        FROM memory_versions
                        GROUP BY memory_id
                    ) latest ON m.id = latest.memory_id
                    JOIN memory_versions mv ON mv.memory_id = latest.memory_id AND mv.version = latest.max_version
                    WHERE m.session_id = ? AND m.user_id = ? AND m.subject = ? AND m.state = 'active'
                """
                cursor.execute(query, (session_id, user_id, subject))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "id": row[0],
                        "content": row[1],
                        "confidence_score": row[2],
                        "source": row[3],
                        "importance": row[4]
                    })
                return result
        except Exception as e:
            memory_logger.error({"event_type": "get_active_memories_failed", "session_id": session_id, "user_id": user_id, "subject": subject, "error": str(e)}, exc_info=True)
            return []

    def retrieve_memories(self, user_id: str, query: str = "", scope: Optional[List[str]] = None, state_filter: str = "active", limit: int = 5) -> List[dict]:
        """
        The unified, strictly deterministic retrieval contract.
        - user_id: Is strictly required. No cross-user joins.
        - state_filter: Determines which lifecycle state to query.
        - scope: List of allowed subjects.
        - limit: Maximum results to return.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # We enforce access control here. Notice there are no shared memories in Phase L6 
                # unless explicitly joined. For now, strict segregation based on user_id.
                
                if scope is None:
                    scope = ["*"]
                    
                allow_all_scope = '*' in scope
                placeholders = ','.join('?' * len(scope)) or "''"
                
                # Deterministic ranking mapped to SQL
                # Priority: manual (3) > imported (2) > inferred (1)
                
                sql = f"""
                    SELECT m.id, m.session_id, m.subject, mv.content, m.confidence_score, m.source, m.created_at, m.state
                    FROM memories m
                    JOIN (
                        SELECT memory_id, MAX(version) as max_version
                        FROM memory_versions
                        GROUP BY memory_id
                    ) latest ON m.id = latest.memory_id
                    JOIN memory_versions mv ON mv.memory_id = latest.memory_id AND mv.version = latest.max_version
                    WHERE m.user_id = ? 
                      AND m.state = ?
                      AND (? OR m.subject IN ({placeholders}))
                """
                
                params = [user_id, state_filter, allow_all_scope] + scope
                
                if query:
                    # Basic keyword LIKE search for v1 (to be replaced by vectors later)
                    sql += " AND mv.content LIKE ?"
                    params.append(f"%{query}%")
                
                # Deterministic Order By
                sql += """
                    ORDER BY 
                        CASE m.source 
                            WHEN 'manual' THEN 3 
                            WHEN 'imported' THEN 2 
                            WHEN 'inferred' THEN 1 
                            ELSE 0 
                        END DESC,
                        m.confidence_score DESC,
                        m.created_at DESC,
                        m.id DESC
                    LIMIT ?
                """
                params.append(limit)
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "session_id": row[1],
                        "subject": row[2],
                        "content": row[3],
                        "confidence_score": row[4],
                        "source": row[5],
                        "created_at": row[6],
                        "state": row[7]
                    })
                    
                return results
                
        except Exception as e:
            memory_logger.error({"event_type": "deterministic_retrieval_failed", "user_id": user_id, "error": str(e)}, exc_info=True)
            return []
            
    def check_rate_limit(self, user_id: str, endpoint: str, max_requests: int, window_seconds: int = 60) -> bool:
        """
        Checks if the user has exceeded the rate limit for an endpoint.
        Returns True if allowed, False if rejected.
        """
        import time
        current_time = int(time.time())
        window_start = current_time - (current_time % window_seconds)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Cleanup old windows
                cursor.execute("DELETE FROM rate_limits WHERE window_start < ?", (current_time - window_seconds,))
                
                cursor.execute("""
                    INSERT INTO rate_limits (user_id, endpoint, window_start, request_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id, endpoint, window_start) 
                    DO UPDATE SET request_count = request_count + 1
                    RETURNING request_count
                """, (user_id, endpoint, window_start))
                
                count = cursor.fetchone()[0]
                conn.commit()
                
                return count <= max_requests
        except Exception as e:
            memory_logger.error({"event_type": "rate_limit_check_failed", "user_id": user_id, "endpoint": endpoint, "error": str(e)}, exc_info=True)
            # Fail closed or open? For infrastructure, fail-open generally unless strictly security. 
            # We'll fail-open locally but log it.
            return True

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
            memory_logger.error({"event_type": "get_overrides_failed", "error": str(e)}, exc_info=True)
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
            memory_logger.error({"event_type": "set_override_failed", "key": key, "error": str(e)}, exc_info=True)
            return False


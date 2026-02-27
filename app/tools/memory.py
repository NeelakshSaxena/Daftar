import datetime
from typing import Optional, List, Dict, Any
from app.logger import tool_logger
from app.settings import load_settings

class MemoryTool:
    def __init__(self, db_instance=None):
        self.db = db_instance
        if self.db is None:
            # Fallback for when tool is initialized without a specific DB instance (e.g. in real run vs tests)
            from app.memory.db import MemoryDB
            self.db = MemoryDB(init_db=False)
            
        from app.memory.policy import PolicyEngine
        self.policy = PolicyEngine(self.db)

    def _normalize_subject(self, subject: str) -> str:
        """Strip whitespace and Title Case the subject for consistency."""
        if not subject:
            return "General"
        return subject.strip().title()

    def _validate_date(self, date_text: str) -> bool:
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def store_memory(self, content: str, memory_date: str, subject: str, importance: int, session_id: str = "default", user_id: str = "default_user", access_mode: str = "private") -> Dict[str, Any]:
        """
        Store a new memory.
        Enforces importance threshold and subject filtering.
        """
        tool_logger.info({
            "event_type": "tool_call_start",
            "tool_name": "store_memory",
            "session_id": session_id,
            "subject": subject,
            "importance": importance
        })

        if not self._validate_date(memory_date):
            reason = f"Invalid date format: {memory_date}. Expected YYYY-MM-DD."
            tool_logger.warning({"event_type": "tool_call_rejected", "tool_name": "store_memory", "reason": reason})
            return {"status": "error", "reason": reason, "notification": "⚠️ Memory not saved (invalid date)", "stored": False}

        if not isinstance(importance, int):
            reason = f"Importance must be an integer, got {type(importance)}."
            tool_logger.warning({"event_type": "tool_call_rejected", "tool_name": "store_memory", "reason": reason})
            return {"status": "error", "reason": reason, "notification": "⚠️ Memory not saved (invalid importance)", "stored": False}

        # Defensive settings loading
        try:
            settings = load_settings(self.db)
        except Exception as e:
            tool_logger.error({"event_type": "settings_load_error", "error": str(e)})
            settings = {}

        # Default safe values
        threshold = 3.0
        try:
            raw_threshold = settings.get("memory_extraction_threshold", 3.0)
            threshold = float(raw_threshold)
        except (ValueError, TypeError):
            tool_logger.warning({"event_type": "malformed_setting", "setting": "memory_extraction_threshold", "value": settings.get("memory_extraction_threshold")})
            threshold = 3.0

        raw_allowed_subjects = settings.get("allowed_subjects", ["*"]) # Default allow all if missing
        if isinstance(raw_allowed_subjects, str):
            import json
            try:
                raw_allowed_subjects = json.loads(raw_allowed_subjects)
            except json.JSONDecodeError:
                pass

        if not isinstance(raw_allowed_subjects, list):
            tool_logger.warning({"event_type": "malformed_setting", "setting": "allowed_subjects", "value": raw_allowed_subjects})
            allowed_subjects = ["*"]
        else:
            allowed_subjects = [self._normalize_subject(s) for s in raw_allowed_subjects]

        norm_subject = self._normalize_subject(subject)

        log_context = {
            "attempted_subject": subject,
            "normalized_subject": norm_subject,
            "importance": importance,
            "threshold": threshold,
            "allowed_subjects": allowed_subjects
        }

        # Enforce threshold
        if importance < threshold:
            reason = "importance_below_threshold"
            tool_logger.info({
                "event_type": "memory_store_rejected",
                "reason": reason,
                **log_context
            })
            return {"status": "rejected", "reason": reason, "detail": f"Importance {importance} is below threshold {threshold}", "notification": "⚠️ Memory not saved (below threshold)", "stored": False}

        # Enforce subject filtering
        if "*" not in allowed_subjects and norm_subject not in allowed_subjects:
            reason = "subject_not_allowed"
            tool_logger.info({
                "event_type": "memory_store_rejected",
                "reason": reason,
                **log_context
            })
            return {"status": "rejected", "reason": reason, "detail": f"Subject '{norm_subject}' is not in allowed subjects.", "notification": "⚠️ Memory not saved (subject not allowed)", "stored": False}

        # Store Memory via Policy Engine
        try:
            import uuid
            correlation_id = str(uuid.uuid4())
            result = self.policy.evaluate_and_store(
                session_id=session_id,
                content=content,
                memory_date=memory_date,
                subject=norm_subject,
                importance=importance,
                user_id=user_id,
                access_mode=access_mode,
                confidence_score=0.6, # LLMs are inferred, so their confidence is hardcapped to 0.6
                source="inferred",
                correlation_id=correlation_id
            )
            return result
        except Exception as e:
            reason = f"policy_unexpected_error: {e}"
            tool_logger.error({
                "event_type": "memory_store_crashed",
                "reason": reason,
                **log_context
            })
            return {"status": "error", "reason": reason, "notification": "❌ Failed to save memory", "stored": False}



    def retrieve_memory(self, query: str = "", scope: Optional[List[str]] = None, state_filter: str = "active", limit: int = 5, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Retrieves memories using the strictly governed Retrieval Contract.
        Enforces scope validation and relays to PolicyEngine.
        """
        import uuid
        correlation_id = str(uuid.uuid4())
        
        tool_logger.info({
            "event_type": "tool_call_start",
            "tool_name": "retrieve_memory",
            "user_id": user_id,
            "query": query,
            "scope": scope,
            "state_filter": state_filter,
            "limit": limit,
            "correlation_id": correlation_id
        })
        
        # Defensive settings loading to validate scope whitelist
        try:
            settings = load_settings(self.db)
            raw_allowed_subjects = settings.get("allowed_subjects", ["*"])
        except Exception as e:
            tool_logger.error({"event_type": "settings_load_error", "error": str(e)})
            raw_allowed_subjects = ["*"]

        if isinstance(raw_allowed_subjects, str):
            import json
            try:
                raw_allowed_subjects = json.loads(raw_allowed_subjects)
            except json.JSONDecodeError:
                pass

        if not isinstance(raw_allowed_subjects, list):
            allowed_subjects = ["*"]
        else:
            allowed_subjects = [self._normalize_subject(s) for s in raw_allowed_subjects]

        # Scope validation
        if scope:
            for s in scope:
                norm_s = self._normalize_subject(s)
                if "*" not in allowed_subjects and norm_s not in allowed_subjects:
                    reason = f"Scope '{norm_s}' is not allowed by current policy settings."
                    tool_logger.warning({
                        "event_type": "tool_call_rejected",
                        "tool_name": "retrieve_memory",
                        "reason": reason,
                        "correlation_id": correlation_id
                    })
                    return {"status": "error", "reason": reason}

        # Format scope for query
        final_scope = [self._normalize_subject(s) for s in scope] if scope else None

        # Execute through Policy Engine
        try:
            result = self.policy.retrieve_memory(
                user_id=user_id,
                query=query,
                scope=final_scope,
                state_filter=state_filter,
                limit=limit,
                correlation_id=correlation_id
            )
            return result
        except Exception as e:
            tool_logger.error({
                "event_type": "retrieval_crashed",
                "reason": str(e),
                "correlation_id": correlation_id
            })
            return {"status": "error", "reason": f"Unexpected retrieval error: {e}"}

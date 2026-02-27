from typing import Dict, Any, Optional, List
import hashlib
import time

from app.memory.db import MemoryDB
from app.logger import memory_logger

class PolicyEngine:
    """
    The strict deterministic lifecycle policy engine governing all memory state transitions.
    """
    def __init__(self, db: MemoryDB):
        self.db = db

    def evaluate_and_store(self, 
                           session_id: str, 
                           content: str, 
                           memory_date: str, 
                           subject: str, 
                           importance: int, 
                           user_id: str = "default_user", 
                           access_mode: str = "private",
                           confidence_score: float = 0.6, # Default for LLM inferred
                           source: str = "inferred",
                           correlation_id: str = "none") -> Dict[str, Any]:
        """
        Evaluates a proposed memory against the current active state and precedence rules.
        Returns a deterministic resolution: ACCEPT, SUPERSEDE, REJECT, or EXISTS.
        """
        memory_logger.info({
            "event_type": "policy_evaluation_started",
            "correlation_id": correlation_id,
            "session_id": session_id,
            "user_id": user_id,
            "subject": subject,
            "source": source
        })

        import time
        import random
        
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            # 1. Fetch active memories for this session/user/subject
            active_memories = self.db.get_active_memories_by_subject(session_id, user_id, subject)

            # Precedence mapping for deterministic resolution
            precedence = {"manual": 3, "imported": 2, "inferred": 1}
            incoming_priority = precedence.get(source, 1)

            # 2. Conflict / Supersede Logic
            conflict_mem = self._find_conflict(content, active_memories)
            
            if conflict_mem:
                # Exact equality check handled heuristically here. DB Constraint is the hard barrier.
                existing_content = conflict_mem['content']
                if content.strip() == existing_content.strip():
                    reason = "EXISTS_REASON_EXACT_MATCH"
                    self._log_policy_decision("EXISTS", reason, correlation_id, session_id, user_id)
                    return {
                        "status": "exists",
                        "notification": "✅ Memory already exists",
                        "stored": False,
                        "detail": "This exact memory was already active.",
                        "reason_code": reason
                    }

                existing_priority = precedence.get(conflict_mem['source'], 1)
                
                # Strict Precedence Rule: Overrule LLM if existing fact is higher priority or same priority with STRICTLY HIGHER confidence
                if incoming_priority < existing_priority or (incoming_priority == existing_priority and confidence_score < conflict_mem['confidence_score']):
                    reason = "REJECT_REASON_PRECEDENCE_TOO_LOW"
                    self._log_policy_decision("REJECT", reason, correlation_id, session_id, user_id, conflicting_id=conflict_mem['id'])
                    return {
                        "status": "rejected",
                        "notification": "⚠️ Memory not saved (lower precedence)",
                        "stored": False,
                        "detail": "A higher or equal priority memory already exists for this topic.",
                        "reason_code": reason
                    }
                else:
                    # SUPERSEDE: Optimistic Concurrency Control (OCC)
                    # We only update if the state is still 'active'.
                    success = self.db.set_memory_state(conflict_mem['id'], "superseded")
                    if not success:
                        # RACE CONDITION TRIGGERED! Another thread mutated this memory before we could.
                        # We must rollback our conceptual state and retry the evaluation from scratch.
                        memory_logger.warning({
                            "event_type": "occ_race_condition",
                            "correlation_id": correlation_id,
                            "attempt": attempt,
                            "memory_id": conflict_mem['id']
                        })
                        time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.05))
                        continue # Retry the loop

                    new_id = self.db.insert_memory(
                        session_id=session_id, content=content, memory_date=memory_date,
                        subject=subject, importance=importance, user_id=user_id, access_mode=access_mode,
                        state="active", supersedes_memory_id=conflict_mem['id'], 
                        confidence_score=confidence_score, source=source, correlation_id=correlation_id
                    )
                    
                    if new_id == -1:
                        # Should be very rare during a supersede, but handled for parity
                        self.db.set_memory_state(conflict_mem['id'], "active") # Rollback conceptual supersede
                        continue

                    reason = "SUPERSEDE_REASON_CONTENT_OVERLAP"
                    self._log_policy_decision("SUPERSEDE", reason, correlation_id, session_id, user_id, supersedes_id=conflict_mem['id'], new_id=new_id)
                    return {
                        "status": "success",
                        "notification": "🧠 Memory updated",
                        "stored": True,
                        "memory_id": new_id,
                        "memory_type": subject.lower(),
                        "summary": "Superseded existing fact",
                        "reason_code": reason
                    }

            # ACCEPT -> No conflicts and passes logical constraints
            new_id = self.db.insert_memory(
                session_id=session_id, content=content, memory_date=memory_date,
                subject=subject, importance=importance, user_id=user_id, access_mode=access_mode,
                state="active", supersedes_memory_id=None, 
                confidence_score=confidence_score, source=source, correlation_id=correlation_id
            )
            
            if new_id == -1:
                # IDENTICAL INSERT FLOOD DETECTED NATIVELY BY DB CONSTRAINT
                reason = "EXISTS_REASON_NATIVE_CONSTRAINT"
                self._log_policy_decision("EXISTS", reason, correlation_id, session_id, user_id)
                return {
                    "status": "exists",
                    "notification": "✅ Memory already exists",
                    "stored": False,
                    "detail": "Native DB constraint blocked identical active memory.",
                    "reason_code": reason
                }

            if not new_id:
                return {"status": "error", "reason": "Failed to store memory"}

            reason = "ACCEPT_REASON_NEW_FACT"
            self._log_policy_decision("ACCEPT", reason, correlation_id, session_id, user_id, new_id=new_id)
            
            return {
                "status": "success",
                "notification": "🧠 Saved to memory",
                "stored": True,
                "memory_id": new_id,
                "memory_type": subject.lower(),
                "summary": content[:50] + "..." if len(content) > 50 else content,
                "reason_code": reason
            }
            
        return {"status": "error", "reason": f"Max OCC retries ({max_retries}) exceeded due to high contention."}

    def _find_conflict(self, new_content: str, active_memories: List[Dict]) -> Optional[Dict]:
        """
        V1 conflict detection: high keyword overlap in the same canonical subject.
        Future optimization: Semantic embeddings.
        """
        words = set(new_content.lower().split())
        for mem in active_memories:
            existing_words = set(mem['content'].lower().split())
            if not words or not existing_words:
                continue
            overlap = len(words.intersection(existing_words)) / min(len(words), len(existing_words))
            # If 60% overlap or more, treat it as a conflict
            if overlap >= 0.6:
                return mem
        return None

    def _log_policy_decision(self, decision: str, reason_code: str, correlation_id: str, session_id: str, user_id: str, conflicting_id: Optional[int] = None, supersedes_id: Optional[int] = None, new_id: Optional[int] = None):
        """Standardized, machine-parseable audit logging for policy decisions."""
        memory_logger.info({
            "event_type": "policy_resolution_decided",
            "correlation_id": correlation_id,
            "user_id": user_id,
            "session_id": session_id,
            "policy_decision": decision,
            "reason_code": reason_code,
            "timestamp": time.time(),
            "conflicting_id": conflicting_id,
            "supersedes_id": supersedes_id,
            "new_id": new_id
        })

    def retrieve_memory(self, user_id: str, query: str = "", scope: Optional[List[str]] = None, state_filter: str = "active", limit: int = 5, correlation_id: str = "none") -> Dict[str, Any]:
        """
        The strictly governed Retrieval Contract.
        No retrieval bypasses the PolicyEngine.
        """
        import time
        start_time = time.time()
        
        # 1. Input Validation
        if not user_id:
            return {"status": "error", "detail": "user_id is strictly required for retrieval."}
            
        allowed_states = {"active", "superseded", "archived", "deleted"}
        if state_filter not in allowed_states:
            return {"status": "error", "detail": f"Invalid state_filter. Must be one of {allowed_states}."}
            
        # Hard cap limit
        actual_limit = min(limit, 20)
        
        # 2. Rate Limiting (50 retrievals per minute)
        is_allowed = self.db.check_rate_limit(user_id=user_id, endpoint="retrieve_memory", max_requests=50, window_seconds=60)
        if not is_allowed:
            memory_logger.warning({
                "event_type": "rate_limit_exceeded",
                "user_id": user_id,
                "endpoint": "retrieve_memory",
                "correlation_id": correlation_id
            })
            return {"status": "error", "detail": "Rate limit exceeded (50 requests per minute).", "notification": "⚠️ Too many retrieval requests."}

        # 3. DB Query (Deterministic, User Isolated)
        results = self.db.retrieve_memories(
            user_id=user_id,
            query=query,
            scope=scope,
            state_filter=state_filter,
            limit=actual_limit
        )

        # 4. Forensic Audit Logging
        # Log exact memory IDs served to whom and when.
        result_ids = [r["id"] for r in results]
        memory_logger.info({
            "event_type": "memory_retrieved_event",
            "correlation_id": correlation_id,
            "user_id": user_id,
            "query": query,
            "scope": scope or ["*"],
            "state_filter": state_filter,
            "result_count": len(results),
            "result_ids": result_ids,
            "duration_ms": int((time.time() - start_time) * 1000)
        })

        return {
            "status": "success",
            "user_id": user_id,
            "query": query,
            "state_filter": state_filter,
            "results": results,
            "result_count": len(results)
        }

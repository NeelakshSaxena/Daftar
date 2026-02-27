import sys
from pathlib import Path
import uuid

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.memory.db import MemoryDB
from app.memory.policy import PolicyEngine

def test_policy_engine():
    db = MemoryDB(init_db=True)
    policy = PolicyEngine(db)
    
    session_id = "test_session"
    user_id = "test_user"
    subject = f"Test_{uuid.uuid4().hex[:8]}"
    
    print(f"--- Testing Policy Engine with isolated subject: {subject} ---")
    
    # 1. Store initial memory (inferred)
    print("\n1. Storing initial inferred memory...")
    res1 = policy.evaluate_and_store(
        session_id=session_id,
        content="User prefers Python for scripts",
        memory_date="2026-02-27",
        subject=subject,
        importance=3,
        user_id=user_id,
        confidence_score=0.6,
        source="inferred"
    )
    assert res1["status"] == "success", f"failed: {res1}"
    assert res1["reason_code"] == "ACCEPT_REASON_NEW_FACT"
    mem1_id = res1["memory_id"]
    print("✅ Initial memory ACCEPTED.")
    
    # 2. Store highly overlapping memory (inferred, same confidence)
    # The current rule says if incoming >= existing priority, and confidence is NOT strictly greater,
    # wait... If it's the SAME priority and SAME confidence, the current rule:
    # `incoming_priority == existing_priority and confidence_score < conflict_mem['confidence_score']`
    # False if they are equal! So it WILL supersede! Let's test that.
    print("\n2. Storing overlapping memory with same inference confidence...")
    res2 = policy.evaluate_and_store(
        session_id=session_id,
        content="User prefers Python for all backend scripts",
        memory_date="2026-02-27",
        subject=subject,
        importance=4,
        user_id=user_id,
        confidence_score=0.6,
        source="inferred"
    )
    assert res2["status"] == "success", f"failed: {res2}"
    assert res2["reason_code"] == "SUPERSEDE_REASON_CONTENT_OVERLAP"
    mem2_id = res2["memory_id"]
    print("✅ Same-confidence overlapping memory SUPERSEDED the old one.")
    
    # 3. Try to supersede with a LOWER confidence inferred memory
    print("\n3. Storing overlapping memory with LOWER confidence...")
    res3 = policy.evaluate_and_store(
        session_id=session_id,
        content="User prefers Python for all scripts and backend",
        memory_date="2026-02-27",
        subject=subject,
        importance=3,
        user_id=user_id,
        confidence_score=0.4, # Lower
        source="inferred"
    )
    assert res3["status"] == "rejected", f"failed: {res3}"
    assert res3["reason_code"] == "REJECT_REASON_PRECEDENCE_TOO_LOW"
    print("✅ Lower-confidence memory REJECTED correctly.")

    # 4. Try to supersede with a HIGHER priority source (manual)
    print("\n4. Storing overlapping memory with HIGHER priority (manual)...")
    res4 = policy.evaluate_and_store(
        session_id=session_id,
        content="User absolutely prefers Python",
        memory_date="2026-02-27",
        subject=subject,
        importance=5,
        user_id=user_id,
        confidence_score=1.0,
        source="manual"
    )
    assert res4["status"] == "success", f"failed: {res4}"
    assert res4["reason_code"] == "SUPERSEDE_REASON_CONTENT_OVERLAP"
    mem4_id = res4["memory_id"]
    print("✅ Manual memory SUPERSEDED the inferred one.")

    # 5. Try to supersede a manual memory with an inferred memory
    print("\n5. Storing inferred memory against manual fact (should reject)...")
    res5 = policy.evaluate_and_store(
        session_id=session_id,
        content="User prefers Python and Rust", # High overlap with mem4
        memory_date="2026-02-27",
        subject=subject,
        importance=4,
        user_id=user_id,
        confidence_score=0.8,
        source="inferred"
    )
    assert res5["status"] == "rejected", f"failed: {res5}"
    assert res5["reason_code"] == "REJECT_REASON_PRECEDENCE_TOO_LOW"
    print("✅ Inferred memory REJECTED against manual fact.")

    print("\n🎉 All Policy Engine precedence tests passed!")

if __name__ == "__main__":
    test_policy_engine()

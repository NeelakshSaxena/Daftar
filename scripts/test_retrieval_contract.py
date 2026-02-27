import sys
from pathlib import Path
import uuid
import time

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.memory.db import MemoryDB
from app.memory.policy import PolicyEngine

def test_retrieval_contract():
    db = MemoryDB(init_db=True)
    policy = PolicyEngine(db)
    
    session_id = "test_session"
    user_a = f"user_A_{uuid.uuid4().hex[:8]}"
    user_b = f"user_B_{uuid.uuid4().hex[:8]}"
    subject = f"TestSubj_{uuid.uuid4().hex[:8]}"
    
    print(f"--- Testing Retrieval Contract ---")

    # 1. User Isolation
    print("\n1. Testing User Isolation...")
    policy.evaluate_and_store(session_id, "User A secret", "2026-02-27", subject, 3, user_a, confidence_score=0.8, source="manual")
    policy.evaluate_and_store(session_id, "User B secret", "2026-02-27", subject, 3, user_b, confidence_score=0.8, source="manual")
    
    res_a = policy.retrieve_memory(user_id=user_a, scope=[subject])
    assert len(res_a["results"]) == 1
    assert res_a["results"][0]["content"] == "User A secret"
    
    res_b = policy.retrieve_memory(user_id=user_b, scope=[subject])
    assert len(res_b["results"]) == 1
    assert res_b["results"][0]["content"] == "User B secret"
    print("✅ User isolation is strictly enforced.")

    # 2. Deterministic Ranking (Priority -> Confidence -> Recency)
    print("\n2. Testing Deterministic Ranking...")
    user_c = f"user_C_{uuid.uuid4().hex[:8]}"
    subj_rank = f"Rank_{uuid.uuid4().hex[:8]}"
    
    # Insert multiple facts for same subject but different content (no 60% overlap so they don't supersede)
    policy.evaluate_and_store(session_id, "Apple", "2026-02-27", subj_rank, 3, user_c, confidence_score=0.6, source="inferred")
    policy.evaluate_and_store(session_id, "Banana", "2026-02-27", subj_rank, 3, user_c, confidence_score=0.8, source="inferred")
    policy.evaluate_and_store(session_id, "Cherry", "2026-02-27", subj_rank, 3, user_c, confidence_score=1.0, source="imported")
    policy.evaluate_and_store(session_id, "Date", "2026-02-27", subj_rank, 3, user_c, confidence_score=1.0, source="manual")
    policy.evaluate_and_store(session_id, "Elderberry", "2026-02-27", subj_rank, 3, user_c, confidence_score=0.9, source="manual")
    
    res_rank = policy.retrieve_memory(user_id=user_c, scope=[subj_rank])
    results = res_rank["results"]
    
    assert len(results) == 5
    # Expected order:
    # 1. Date (manual, 1.0)
    # 2. Elderberry (manual, 0.9)
    # 3. Cherry (imported, 1.0)
    # 4. Banana (inferred, 0.8)
    # 5. Apple (inferred, 0.6)
    
    assert results[0]["content"] == "Date"
    assert results[1]["content"] == "Elderberry"
    assert results[2]["content"] == "Cherry"
    assert results[3]["content"] == "Banana"
    assert results[4]["content"] == "Apple"
    print("✅ Deterministic ranking (Priority > Confidence) correctly enforced.")

    # 3. State Filtering (Superseded is hidden)
    print("\n3. Testing State Filtering (Hiding Superseded)...")
    user_d = f"user_D_{uuid.uuid4().hex[:8]}"
    subj_state = f"State_{uuid.uuid4().hex[:8]}"
    
    # Store inferred, then supersede it with manual
    policy.evaluate_and_store(session_id, "I like dogs", "2026-02-27", subj_state, 3, user_d, confidence_score=0.6, source="inferred")
    policy.evaluate_and_store(session_id, "I primarily like cats", "2026-02-27", subj_state, 5, user_d, confidence_score=1.0, source="manual")
    
    # Retrieve active
    res_active = policy.retrieve_memory(user_id=user_d, scope=[subj_state], state_filter="active")
    assert len(res_active["results"]) == 1
    assert res_active["results"][0]["content"] == "I primarily like cats"
    
    # Retrieve superseded explicitly (auditing)
    res_superseded = policy.retrieve_memory(user_id=user_d, scope=[subj_state], state_filter="superseded")
    assert len(res_superseded["results"]) == 1
    assert res_superseded["results"][0]["content"] == "I like dogs"
    print("✅ Active default hides superseded lineage. Explicit request allows auditing.")

    # 4. Hard Cap Limit
    print("\n4. Testing Hard Cap Limit...")
    res_limit = policy.retrieve_memory(user_id=user_c, scope=[subj_rank], limit=100)
    # Total available is 5, but let's test the cap logic. If there were 25, it would cap at 20.
    # We will simulate the DB check directly or just know the limit parameter didn't crash.
    # To truly test the cap, we'd insert 25. Let's insert 21 for user E.
    user_e = f"user_E_{uuid.uuid4().hex[:8]}"
    for i in range(25):
        policy.evaluate_and_store(session_id, f"Fact {i}", "2026-02-27", "Spam", 3, user_e, confidence_score=0.5, source="inferred")
    
    res_cap = policy.retrieve_memory(user_id=user_e, scope=["Spam"], limit=50)
    assert len(res_cap["results"]) == 20
    print("✅ Max retrieval limit strictly capped at 20.")

    # 5. Rate Limiting
    print("\n5. Testing Rate Limiting (50 per minute)...")
    user_f = f"user_F_{uuid.uuid4().hex[:8]}"
    # 50 allowed
    for _ in range(50):
        res = policy.retrieve_memory(user_id=user_f)
        assert res["status"] == "success"
        
    # 51st should fail
    res_fail = policy.retrieve_memory(user_id=user_f)
    assert res_fail["status"] == "error"
    assert "Rate limit exceeded" in res_fail["detail"]
    print("✅ Rate Limiting stops abuse past 50 requests/min.")

    print("\n🎉 All Retrieval Contract integration tests passed!")


if __name__ == "__main__":
    test_retrieval_contract()

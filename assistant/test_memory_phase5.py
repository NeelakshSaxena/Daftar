import os
from datetime import datetime
from memory.db import MemoryDB

def test_daily_aggregation():
    print("--- Phase 5: Daily Aggregation Test ---")
    
    db = MemoryDB()
    session_id = "test_daily_agg_session"
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Store memories with various importances
    db.store_memory(session_id, "User played tennis", today, "Health", 2)
    db.store_memory(session_id, "User had a team meeting", today, "Work", 3)
    db.store_memory(session_id, "User deployed system to production", today, "Work", 5)
    
    # Store a memory for another day just to be sure it doesn't get aggregated
    db.store_memory(session_id, "User went to the dentist", "2020-01-01", "Health", 4)
    
    # 2. Get daily aggregation with threshold 3
    agg = db.get_daily_aggregation(session_id, today, min_importance=3)
    
    # Validation
    assert "Work" in agg, "Work subject should be present"
    work_events = agg["Work"]
    assert len(work_events) == 2, f"Expected 2 work events, got {len(work_events)}"
    
    importances = [e["importance"] for e in work_events]
    assert 5 in importances, "Importance 5 should be present"
    assert 3 in importances, "Importance 3 should be present"
    
    assert "Health" not in agg, "Health item with importance 2 should have been filtered out"
    
    print("✅ Daily Aggregation Test Passed")
    print("   - Successfully excluded importance 2")
    print("   - Successfully included importance 3 and 5")
    print("   - Successfully grouped by subject")
    print("   - Returned correct rich structure")

if __name__ == "__main__":
    try:
        test_daily_aggregation()
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

import sys
import os
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.memory.db import MemoryDB
from app.tools.memory import MemoryTool

def test_payloads():
    db = MemoryDB(init_db=True)
    tool = MemoryTool(db_instance=db)
    
    print("Testing error: invalid date...")
    res1 = tool.store_memory("content", "invalid-date", "General", 4)
    assert res1.get("notification") == "⚠️ Memory not saved (invalid date)"
    assert res1.get("stored") == False
    
    print("Testing error: importance below threshold...")
    # by default threshold is 3.0
    res2 = tool.store_memory("trivial", "2026-02-27", "General", 1)
    assert res2.get("notification") == "⚠️ Memory not saved (below threshold)"
    assert res2.get("stored") == False

    print("Testing success payload structure...")
    unique_subject = f"Pref_{uuid.uuid4().hex[:8]}"
    unique_content = f"User loves Python for backend development {uuid.uuid4()}"
    res3 = tool.store_memory(unique_content, "2026-02-27", unique_subject, 5)
    assert res3.get("notification") in ["🧠 Saved to memory", "🧠 Memory updated"]
    assert res3.get("stored") == True
    assert res3.get("memory_type") == unique_subject.lower()
    
    # Store ID to clear it later or test duplicate
    print("Testing duplicate memory payload...")
    res4 = tool.store_memory(unique_content, "2026-02-27", unique_subject, 5)
    assert res4.get("status") == "exists"
    assert res4.get("notification") == "✅ Memory already exists"
    assert res4.get("stored") == False
    assert res4.get("summary") == "Duplicate memory ignored"


    print("✅ All payload tests passed.")
    
if __name__ == "__main__":
    test_payloads()

from memory.db import MemoryDB
import time

def run_tests():
    db = MemoryDB()
    session_id = f"test_{int(time.time())}"
    
    print(f"Running Phase 4 Tests on session {session_id}...\n")
    
    print("--- 1. Store Memory ---")
    mem_id = db.store_memory(session_id, "I like apples.")
    print(f"Stored memory_id: {mem_id}")
    assert mem_id is not None, "Failed to store memory"
    
    # Store duplicate
    dup_id = db.store_memory(session_id, "I like apples.")
    print(f"Duplicate store returned: {dup_id}")
    assert dup_id is None, "Should not store duplicate memory"
    
    print("\n--- 2. Retrieve Initial Memory ---")
    mems = db.retrieve_recent_memories(session_id)
    print(f"Retrieved: {mems}")
    assert len(mems) == 1, "Should retrieve exactly one memory"
    assert mems[0] == "I like apples.", "Content mismatch"
    
    print("\n--- 3. Edit Memory ---")
    success = db.edit_memory(mem_id, "I absolutely love apples and bananas.", session_id)
    print(f"Edit success: {success}")
    assert success is True, "Failed to edit memory"
    
    print("\n--- 4. Verify Monotonic Increment (Edit Twice) ---")
    success2 = db.edit_memory(mem_id, "I ONLY eat bananas now.", session_id)
    print(f"Edit 2 success: {success2}")
    assert success2 is True, "Failed to edit memory second time"
    
    print("\n--- 5. Retrieve Latest Memory ---")
    mems2 = db.retrieve_recent_memories(session_id)
    print(f"Retrieved: {mems2}")
    assert len(mems2) == 1, "Should retrieve exactly one memory"
    assert mems2[0] == "I ONLY eat bananas now.", "Content should match latest edit"
    
    print("\n--- 6. Verify Old Versions Still Exist ---")
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version, content FROM memory_versions WHERE memory_id = ? ORDER BY version", (mem_id,))
        versions = cursor.fetchall()
        print(f"All versions in DB: {versions}")
        assert len(versions) == 3, "There should be 3 versions in DB"
        assert versions[0][0] == 1 and versions[0][1] == "I like apples.", "V1 mismatch"
        assert versions[1][0] == 2 and versions[1][1] == "I absolutely love apples and bananas.", "V2 mismatch"
        assert versions[2][0] == 3 and versions[2][1] == "I ONLY eat bananas now.", "V3 mismatch"
        
    print("\n--- 7. Edit Non-existent Memory ---")
    bad_edit = db.edit_memory(999999, "Failure path test")
    print(f"Bad edit success: {bad_edit}")
    assert bad_edit is False, "Should fail on editing a non-existent memory"
    
    # Optional: Edit with wrong session ID
    wrong_session_edit = db.edit_memory(mem_id, "Wrong session hack", "fake_session")
    print(f"Wrong session edit success: {wrong_session_edit}")
    assert wrong_session_edit is False, "Should fail when session ID doesn't match"

    print("\n✅ All Phase 4 DB Versioning tests passed!")

if __name__ == "__main__":
    run_tests()

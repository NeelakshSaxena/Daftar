import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
from app.memory.db import MemoryDB
from datetime import datetime

from app.llm_client import LLMClient

API_URL = "http://127.0.0.1:8000/chat"

def test_auth_and_isolation():
    print("--- Phase 7: Authentication and Isolation Tests ---")

    # 1. Test missing token
    print("1. Testing missing token...")
    resp = client.post("/chat", json={"message": "Hello"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    data = resp.json()
    assert data["error"] == "Unauthorized"

    # 2. Test invalid token
    print("2. Testing invalid token...")
    resp = client.post(
        "/chat", 
        json={"message": "Hello"}, 
        headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    # Set up DB for isolation test
    print("3. Setting up mock memories for cross-user isolation...")
    db = MemoryDB()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Insert private memory for user_1
    db.store_memory(
        session_id="test_session_u1",
        content="User 1 secret project",
        memory_date=today,
        subject="Work",
        importance=5,
        user_id="user_1",
        access_mode="private"
    )
    
    # Insert private memory for admin_1 (user 2)
    db.store_memory(
        session_id="test_session_admin",
        content="Admin secret master plan",
        memory_date=today,
        subject="Work",
        importance=5,
        user_id="admin_1",
        access_mode="private"
    )
    
    # 4. Test User 1 cannot see Admin's memory
    print("4. Testing Admin memory isolated from User 1...")
    user1_memories = db.retrieve_recent_memories(
        session_id="test_session_admin", 
        user_id="user_1", 
        allowed_subjects=["Work"]
    )
    assert len(user1_memories) == 0, "User 1 should not see Admin's private memory!"

    # 5. Test User 1 can see their own memory
    print("5. Testing User 1 can see their own memory...")
    user1_own_memories = db.retrieve_recent_memories(
        session_id="test_session_u1", 
        user_id="user_1", 
        allowed_subjects=["Work"]
    )
    assert len(user1_own_memories) > 0, "User 1 should see their own memory!"
    assert "User 1 secret project" in user1_own_memories[0]

    # 6. Test Shared memory
    print("6. Testing shared memory access...")
    db.store_memory(
        session_id="test_session_shared",
        content="Company wide announcement",
        memory_date=today,
        subject="Work",
        importance=3,
        user_id="admin_1",
        access_mode="shared"
    )
    
    user1_shared = db.retrieve_recent_memories(
        session_id="test_session_shared", 
        user_id="user_1", 
        allowed_subjects=["Work"]
    )
    assert len(user1_shared) > 0, "User 1 should see the shared memory!"
    assert "Company wide announcement" in user1_shared[0]

    # 7. Test subject restriction on shared memory
    print("7. Testing subject restriction on shared memory...")
    db.store_memory(
        session_id="test_session_shared_health",
        content="Health tip for everyone",
        memory_date=today,
        subject="Health",
        importance=3,
        user_id="admin_1",
        access_mode="shared"
    )
    
    user1_shared_health = db.retrieve_recent_memories(
        session_id="test_session_shared_health", 
        user_id="user_1", 
        allowed_subjects=["Work"]
    )
    assert len(user1_shared_health) == 0, "User 1 should NOT see the shared Health memory because of subject restriction!"

    print("✅ All authentication and cross-user isolation tests passed!")

if __name__ == "__main__":
    try:
        test_auth_and_isolation()
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

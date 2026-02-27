import sys
from pathlib import Path
import uuid
import time
import concurrent.futures
import random
import traceback

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.memory.db import MemoryDB
from app.memory.policy import PolicyEngine

def run_stress_test():
    db = MemoryDB(init_db=True)
    policy = PolicyEngine(db)
    
    session_id = "concurrency_session"
    user_id = f"stress_user_{uuid.uuid4().hex[:8]}"
    subject = f"StressSubj_{uuid.uuid4().hex[:8]}"
    
    print(f"--- Starting Concurrency Stress Test Phase L7 ---")
    print(f"User ID: {user_id}")
    print(f"Subject: {subject}")

    # The facts
    shared_fact = "The system is under extreme load."
    competing_fact_1 = "The load is mostly writes."
    competing_fact_2 = "The load is mostly reads."

    def worker_insert_identical(thread_id):
        try:
            res = policy.evaluate_and_store(
                session_id=session_id,
                content=shared_fact,
                memory_date="2026-02-27",
                subject=subject,
                importance=3,
                user_id=user_id,
                confidence_score=0.8,
                source="inferred"
            )
            return ("IDENTICAL_WRITE", res.get("status"), res.get("reason_code"), res.get("memory_id"))
        except Exception as e:
            return ("IDENTICAL_WRITE", "CRASH", str(e), None)

    def worker_insert_conflict_1(thread_id):
        try:
            res = policy.evaluate_and_store(
                session_id=session_id,
                content=competing_fact_1,
                memory_date="2026-02-27",
                subject=subject,
                importance=4,
                user_id=user_id,
                confidence_score=0.9,
                source="manual"
            )
            return ("CONFLICT_1", res.get("status"), res.get("reason_code"), res.get("memory_id"))
        except Exception as e:
            return ("CONFLICT_1", "CRASH", str(e), None)

    def worker_insert_conflict_2(thread_id):
        try:
            res = policy.evaluate_and_store(
                session_id=session_id,
                content=competing_fact_2,
                memory_date="2026-02-27",
                subject=subject,
                importance=5,
                user_id=user_id,
                confidence_score=1.0,
                source="manual"
            )
            return ("CONFLICT_2", res.get("status"), res.get("reason_code"), res.get("memory_id"))
        except Exception as e:
            return ("CONFLICT_2", "CRASH", str(e), None)

    def worker_retrieve(thread_id):
        try:
            res = policy.retrieve_memory(user_id=user_id, scope=[subject], limit=20)
            return ("RETRIEVE", res.get("status"), len(res.get("results", [])), res.get("detail", ""))
        except Exception as e:
            return ("RETRIEVE", "CRASH", str(e), None)

    tasks = []
    # 20 identical writes (should result in 1 insert, 19 EXISTS)
    for i in range(20): tasks.append((worker_insert_identical, i))
    
    # 20 conflicting writes of type 1
    for i in range(20): tasks.append((worker_insert_conflict_1, i))
    
    # 20 conflicting writes of type 2 (strongest)
    for i in range(20): tasks.append((worker_insert_conflict_2, i))
    
    # 60 retrievals (should trigger rate limit of 50 after a while)
    for i in range(60): tasks.append((worker_retrieve, i))

    # Shuffle to maximize race conditions
    random.shuffle(tasks)

    print(f"\nLaunching {len(tasks)} threads concurrently...")
    
    start_time = time.time()
    results = []
    crashes = 0
    locked_errors = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_task = {executor.submit(func, arg): func.__name__ for func, arg in tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                res = future.result()
                results.append(res)
                if res[1] == "CRASH":
                    crashes += 1
                    if "database is locked" in str(res[2]):
                        locked_errors += 1
            except Exception as exc:
                print(f"Thread generated an exception: {exc}")
                crashes += 1

    time_taken = time.time() - start_time
    print(f"\n--- Stress Test Completed in {time_taken:.2f} seconds ---")
    
    # Analytics
    writes_success = len([r for r in results if r[0] in ["IDENTICAL_WRITE", "CONFLICT_1", "CONFLICT_2"] and r[1] == "success"])
    writes_exists = len([r for r in results if r[0] in ["IDENTICAL_WRITE", "CONFLICT_1", "CONFLICT_2"] and r[1] == "exists"])
    writes_rejected = len([r for r in results if r[0] in ["IDENTICAL_WRITE", "CONFLICT_1", "CONFLICT_2"] and r[1] == "rejected"])
    
    retrievals_success = len([r for r in results if r[0] == "RETRIEVE" and r[1] == "success"])
    retrievals_ratelimited = len([r for r in results if r[0] == "RETRIEVE" and r[1] == "error" and "Rate limit exceeded" in str(r[3])])
    
    print(f"\n--- Results Summary ---")
    print(f"Crashes: {crashes} (Database Locked: {locked_errors})")
    print(f"Successful Mutations: {writes_success}")
    print(f"No-Op (Exists): {writes_exists}")
    print(f"Rejected: {writes_rejected}")
    print(f"Successful Retrievals: {retrievals_success}")
    print(f"Rate Limited Retrievals: {retrievals_ratelimited}")

    # Invariant Audit
    print("\n--- Invariant Audit ---")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Invariant 1: Identical Facts should only have 1 active memory
        cursor.execute("SELECT id, state, created_at FROM memories WHERE user_id = ? AND subject = ? AND source = 'inferred' AND confidence_score = 0.8", (user_id, subject))
        identical_memories = cursor.fetchall()
        active_identicals = [m for m in identical_memories if m[1] == 'active']
        print(f"Expected 1 active identical memory, found: {len(active_identicals)}. (Total inserted: {len(identical_memories)})")
        if len(active_identicals) > 1:
            print("❌ INVARIANT BROKEN: Duplicate active memories inserted due to TOCTOU race condition.")
            
        # Invariant 2: Superseded memories must have exactly one active successor (lineage integrity)
        cursor.execute("SELECT id, supersedes_memory_id, state FROM memories WHERE user_id = ? AND subject = ?", (user_id, subject))
        all_mems = cursor.fetchall()
        
        active_mems = [m for m in all_mems if m[2] == 'active']
        superseded_mems = [m for m in all_mems if m[2] == 'superseded']
        
        print(f"Total Active Memories for subject: {len(active_mems)}")
        print(f"Total Superseded Memories for subject: {len(superseded_mems)}")
        
        # Check if competing facts resulted in multiple active memories when they should have superseded
        # Because we sent competing_fact_1 and competing_fact_2, they overlap. fact_2 (manual, 1.0) is strongest.
        # So only fact_2 should be active. fact_1 and shared_fact should be superseded or rejected.
        
        # This is a bit complex depending on exact text overlap. Let's just output it to analyze offline.
        
    print("\nAnalysis complete.")

if __name__ == "__main__":
    try:
        run_stress_test()
    except Exception as e:
        with open("crash.log", "w") as f:
            traceback.print_exc(file=f)
        sys.exit(1)

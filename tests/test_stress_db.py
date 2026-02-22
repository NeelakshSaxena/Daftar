import threading
import concurrent.futures
import time
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.memory.db import MemoryDB
from app.llm_client import LLMClient


def thread_worker(db, index):
    try:
        # Grab threshold directly from DB overrides
        overrides = db.get_all_overrides()
        threshold = float(overrides.get("memory_extraction_threshold", 0.6))
        
        # Simulate storing memory
        session_id = f"stress_session_{index}"
        mem_id = db.store_memory(
            session_id=session_id,
            content=f"Stress test memory {index}",
            memory_date="2026-02-22",
            subject="Test",
            importance=5
        )
        return True, mem_id
    except Exception as e:
        return False, str(e)

def run_stress_test():
    db = MemoryDB(init_db=True) # Ensure DB exists
    db.set_setting_override("memory_extraction_threshold", "0.9")
    
    num_threads = 50
    success_count = 0
    error_count = 0
    
    print(f"Starting concurrency stress test with {num_threads} threads...")
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(thread_worker, db, i) for i in range(num_threads)]
        
        for future in concurrent.futures.as_completed(futures):
            success, result = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1
                if error_count <= 5: # Print first few errors
                    print(f"Thread Error: {result}")
                    
    duration = time.time() - start_time
    print(f"Stress test completed in {duration:.2f} seconds.")
    print(f"Successes: {success_count}/{num_threads}")
    print(f"Errors: {error_count}/{num_threads}")
    
    if error_count > 0:
        print("❌ Concurrency test failed due to errors.")
        sys.exit(1)
    else:
        print("✅ Concurrency test passed entirely.")

if __name__ == "__main__":
    run_stress_test()

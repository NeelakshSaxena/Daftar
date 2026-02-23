import sys
import os
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from mcp_adapter import read_file

def test_attack(name, payload):
    print(f"Testing Attack: {name}")
    print(f"Payload: {payload}")
    try:
        content = read_file(payload)
        if content.startswith("Error:"):
            print(f"[PASS] Blocked with error string: {content}")
            return True
        print("[FAIL] Attack succeeded (path was read)!")
        return False
    except Exception as e:
        print(f"[WARN] UNEXPECTED: {type(e).__name__}: {e}")
        return False

def test_concurrency():
    print("\nTesting Concurrency (20 parallel reads)...")
    successes = 0
    failures = 0
    lock = threading.Lock()
    
    def worker():
        nonlocal successes, failures
        try:
            content = read_file("requirements.txt")
            if "fastapi" in content.lower():
                with lock:
                    successes += 1
            else:
                with lock:
                    failures += 1
        except Exception as e:
            print(f"Concurrent thread failed: {e}")
            with lock:
                failures += 1
                
    threads = []
    start_time = time.time()
    for _ in range(20):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    print(f"Concurrency results: {successes} passed, {failures} failed in {duration:.3f}s")
    return failures == 0

if __name__ == "__main__":
    print("--- Running Security Hardening Tests ---")
    
    attacks = [
        ("Absolute Path Posix", "/etc/passwd"),
        ("Traverse Posix", "/../../etc/passwd"),
        ("Traverse Windows", "\\..\\..\\..\\Windows\\System32\\drivers\\etc\\hosts"),
        ("Direct Drive Windows", "C:\\Windows\\System32\\config\\SAM"),
        ("Nested Traversal", "frontend/../../mcp.json"),
        ("Absolute Posix Inner", "/frontend/index.html")
    ]
    
    attack_failures = 0
    for name, payload in attacks:
        if not test_attack(name, payload):
            attack_failures += 1
            
    if attack_failures > 0:
        print(f"\n[FAIL] SECURITY BREACH: {attack_failures} attacks succeeded.")
        sys.exit(1)
        
    if not test_concurrency():
        print("\n[FAIL] CONCURRENCY FAILED.")
        sys.exit(1)
        
    print("\n[PASS] All security and stress tests passed successfully.")
    

import os
import concurrent.futures
from uuid import uuid4
from llm_client import LLMClient
from memory.manager import MemoryManager

# We will mock the OpenAI call inside LLMClient for this stress test
# so it runs instantly without needing LM Studio.
import llm_client
import threading
import time

class MockCompletions:
    def create(self, **kwargs):
        class Msg:
            content = "Mocked Response"
        class Choice:
            message = Msg()
        class Resp:
            choices = [Choice()]
        time.sleep(0.01) # Simulate slight I/O delay to encourage race condition
        return Resp()

class MockChat:
    completions = MockCompletions()

class MockClient:
    def __init__(self, **kwargs):
        self.chat = MockChat()

llm_client.OpenAI = MockClient

def test_concurrent_writes():
    print("--- Starting STRESS TEST: Concurrent Same-Session Requests ---")
    client = LLMClient()
    session_id = "stress_test_session"
    
    # Ensure clean slate
    m = MemoryManager()
    filepath = m._get_file_path(session_id)
    if os.path.exists(filepath):
        os.remove(filepath)

    def worker(i):
        try:
            client.chat(f"Message {i}", session_id=session_id)
            return True
        except Exception as e:
            print(f"Worker {i} failed: {e}")
            return False

    num_threads = 50
    print(f"Hammering session '{session_id}' with {num_threads} concurrent messages...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    # Validate output
    history = m.load(session_id)
    print(f"Final saved history length: {len(history)}")
    
    # Each request adds 1 user message, 1 assistant message.
    # We sent 50 requests (100 messages total).
    # Expected: The final history should be exactly MAX_CHAT_HISTORY (20).
    # And there should be NO duplicates/corruption.
    
    if len(history) == 20:
        print("✅ SUCCESS: History length is perfectly truncated at 20.")
    else:
        print(f"❌ FAILED: History length is {len(history)} (expected 20).")
        
    print(f"Sample old message: {history[0]['content']}")
    print(f"Sample recent message: {history[-1]['content']}")
    
    if os.path.exists(filepath):
        os.remove(filepath)
    print("--- Stress Test Complete ---")

if __name__ == "__main__":
    test_concurrent_writes()

import os
import json
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.memory.manager import MemoryManager

print('--- Starting MemoryManager Tests ---')
m = MemoryManager()
session_id = "test_prune_session"

# ensure clean state
file_path = m._get_file_path(session_id)
if os.path.exists(file_path): os.remove(file_path)

# Test 1: Save 25 messages, then load and prune
history = []
for i in range(25):
    history.append({'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'msg {i}'})

pruned = m.prune(history)
print(f"Pruned length from 25: {len(pruned)} (expected 20)")
m.save(session_id, pruned)

loaded = m.load(session_id)
print(f"Loaded length: {len(loaded)} (expected 20)")
print(f"First loaded msg: {loaded[0]['content']} (expected msg 5)")
print(f"Last loaded msg: {loaded[-1]['content']} (expected msg 24)")

# Test 2: Prune with reserve=1
pruned_reserve = m.prune(loaded, reserve=1)
print(f"Pruned with reserve 1 length: {len(pruned_reserve)} (expected 19)")

# Test 3: System prompt filter
loaded.insert(0, {'role': 'system', 'content': 'I am a system prompt'})
m.save(session_id, loaded)
filtered = m.load(session_id)
has_system = any(msg['role'] == 'system' for msg in filtered)
print(f"System prompt filtered on load: {not has_system} (expected True)")

# Clean up
if os.path.exists(file_path): os.remove(file_path)
print('--- Tests Complete ---')

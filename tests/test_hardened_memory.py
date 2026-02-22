import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch, MagicMock
from app.memory.db import MemoryDB
from app.memory.manager import MemoryManager
from app.llm_client import LLMClient

def test_hardened_extraction():
    client = LLMClient()
    
    with patch('app.llm_client.OpenAI') as MockOpenAI:
        mock_instance = MockOpenAI.return_value
        mock_response = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_response
        
        # 1. Hallucinated Array for Subject
        mock_response.choices[0].message.content = '{"content": "I worked.", "subject": ["Work", "Office"], "importance": "high"}'
        res = client._extract_memory_sync("text", "http://fake")
        assert res is not None
        assert res["subject"] == "Work", f"Expected 'Work', got {res['subject']}"
        assert res["importance"] == 5, f"Expected 5, got {res['importance']}"
        print("✅ Correctly parsed array subject and 'high' importance string.")

        # 2. Hallucinated Dict for Content
        mock_response.choices[0].message.content = '{"content": {"action": "Run", "time": "morning"}, "subject": "Health", "importance": "low"}'
        res2 = client._extract_memory_sync("text", "http://fake")
        assert res2 is not None
        assert "action" in res2["content"], f"Content dict wasn't cast to string: {res2['content']}"
        assert res2["importance"] == 1, f"Expected 1, got {res2['importance']}"
        print("✅ Correctly parsed dictionary content and 'low' importance string.")
        
if __name__ == "__main__":
    try:
        test_hardened_extraction()
        print("All hardening validations passed!")
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")

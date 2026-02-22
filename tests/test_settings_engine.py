import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import uuid
from datetime import datetime
from app.memory.db import MemoryDB
from app.memory.manager import MemoryManager
from app.llm_client import LLMClient
from unittest.mock import patch, MagicMock


def test_dynamic_threshold():
    client = LLMClient()
    db = MemoryDB()
    session_id = f"test_dynamic_{uuid.uuid4().hex}"

    
    # 1. Ensure default threshold is 0.6
    db.set_setting_override("memory_extraction_threshold", "0.6")
    
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '```json\n{"content": "Got a dog.", "subject": "Personal", "importance": 4}\n```'
    
    with patch('app.llm_client.OpenAI') as MockOpenAI:
        mock_instance = MockOpenAI.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        reply, saved = client.chat("I got a dog for my birthday.", api_url="http://127.0.0.1:1234/v1", session_id=session_id)
        assert saved is True, "Expected memory to be saved at importance 4 (0.8 >= 0.6)"
        print("✅ Memory saved with importance 4 under default threshold 0.6.")
        
    # 2. Change threshold to 0.9
    db.set_setting_override("memory_extraction_threshold", "0.9")
    
    mock_response2 = MagicMock()
    mock_response2.choices[0].message.content = '```json\n{"content": "Got a cat.", "subject": "Personal", "importance": 4}\n```'
    
    with patch('app.llm_client.OpenAI') as MockOpenAI:
        mock_instance = MockOpenAI.return_value
        mock_instance.chat.completions.create.return_value = mock_response2
        
        reply, saved = client.chat("I got a cat for my birthday.", api_url="http://127.0.0.1:1234/v1", session_id=session_id)
        assert saved is False, "Expected memory to NOT be saved at importance 4 (0.8 < 0.9)"
        print("✅ Memory skipped with importance 4 under new threshold 0.9.")
        
if __name__ == "__main__":
    try:
        test_dynamic_threshold()
        print("Settings Engine validations passed!")
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")

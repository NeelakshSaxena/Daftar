import sys
from unittest.mock import patch, MagicMock
from llm_client import LLMClient

def test_extraction():
    client = LLMClient()
    
    # 1. Normal valid case
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '```json\n{"content": "User loves pytest.", "subject": "Tech", "importance": 4}\n```'
    
    with patch('llm_client.OpenAI') as MockOpenAI:
        mock_instance = MockOpenAI.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        res = client._extract_memory_sync("I love pytest", "http://fake")
        assert res is not None, "Expected valid memory"
        assert res["content"] == "User loves pytest.", f"Got {res['content']}"
        assert res["subject"] == "Tech"
        assert res["importance"] == 4
        print("✅ Normal extraction parsed safely.")

        # 2. Missing key validation (no subject)
        mock_response.choices[0].message.content = '{"content": "Missing subject."}'
        res2 = client._extract_memory_sync("I love pytest", "http://fake")
        assert res2 is None, "Should reject if missing keys"
        print("✅ Missing keys properly rejected.")
        
        # 3. Test importance clamp (10 -> 5)
        mock_response.choices[0].message.content = '{"content": "Super!", "subject": "Tech", "importance": 10}'
        res3 = client._extract_memory_sync("Wow", "http://fake")
        assert res3 is not None
        assert res3["importance"] == 5, f"Expected 5, got {res3['importance']}"
        print("✅ Importance >5 clamped to 5.")
        
        # 4. Test importance clamp (-2 -> 1)
        mock_response.choices[0].message.content = '{"content": "Low!", "subject": "Tech", "importance": -2}'
        res4 = client._extract_memory_sync("Wow", "http://fake")
        assert res4 is not None
        assert res4["importance"] == 1, f"Expected 1, got {res4['importance']}"
        print("✅ Importance <1 clamped to 1.")

        # 5. Missing importance defaults to 3
        mock_response.choices[0].message.content = '{"content": "Default importance.", "subject": "Tech"}'
        res5 = client._extract_memory_sync("Wow", "http://fake")
        assert res5 is not None
        assert res5["importance"] == 3, f"Expected 3, got {res5['importance']}"
        print("✅ Missing importance defaults to 3.")

if __name__ == "__main__":
    try:
        test_extraction()
        print("All format validations passed!")
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")

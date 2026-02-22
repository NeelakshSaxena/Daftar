from llm_client import LLMClient
import time

URL = "http://172.17.72.151:1234/v1"
SESSION_ID = f"test_{int(time.time())}"
client = LLMClient()

def chat(message: str):
    print(f"\nUser: {message}")
    reply, saved = client.chat(message, api_url=URL, session_id=SESSION_ID)
    print(f"Assistant (Memory Saved: {saved}): {reply}")

def run_tests():
    print("--- 1. Normal chat ---")
    chat("Hello, how are you today?")
    
    print("\n--- 2. Factual Memory (Allergy) ---")
    chat("I am severely allergic to peanuts.")
    
    print("\n--- 3. Negative case (Emotion) ---")
    chat("I feel very sad today.")
    
    print("\n--- 4. Recall Test ---")
    chat("What am I allergic to? Be brief.")

if __name__ == "__main__":
    run_tests()

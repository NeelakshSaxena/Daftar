from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
import re

app = FastAPI()

class ChatRequest(BaseModel):
    model: str
    messages: list
    temperature: float = 0.7

@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    messages = req.messages
    system_prompt = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    user_msg = messages[-1]["content"] if messages and messages[-1]["role"] == "user" else ""
    
    # Check if this is the memory extraction call
    if "Extract ONLY stable, factual" in system_prompt:
        if "sad" in user_msg.lower():
            content = "NONE"
        elif "allergic" in user_msg.lower():
            content = '{"content": "User is allergic to peanuts.", "subject": "Health", "importance": 5}'
        elif "buy a house" in user_msg.lower():
            content = '{"content": "User wants to buy a new house.", "subject": "Finance", "importance": 4}'
        elif "learn piano" in user_msg.lower():
            content = '{"content": "User is learning piano.", "subject": "Hobbies", "importance": 2}'
        elif "went to the gym" in user_msg.lower():
            content = '{"content": "User went to the gym.", "subject": "Health", "importance": 3}'
        elif "had a team meeting" in user_msg.lower():
            content = '{"content": "User had a team meeting.", "subject": "Work", "importance": 4}'
        elif "deployed to production" in user_msg.lower():
            content = '{"content": "User deployed system to production.", "subject": "Work", "importance": 5}'
        elif "played tennis" in user_msg.lower():
            content = '{"content": "User played tennis.", "subject": "Health", "importance": 2}'
        else:
            content = "NONE"
        return {
            "choices": [
                {
                    "message": {
                        "content": content
                    }
                }
            ]
        }
    
    # Main chat generation
    if "allergic to peanuts" in system_prompt:
        reply = "You are allergic to peanuts based on my memory."
    else:
        reply = f"I am a mock response to: {user_msg}"
        
    return {
        "choices": [
            {
                "message": {
                    "content": reply
                }
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=1234)

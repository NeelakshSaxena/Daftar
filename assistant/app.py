from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from llm_client import LLMClient

app = FastAPI(title="Assistant API")

llm_client = LLMClient()

class ChatRequest(BaseModel):
    message: str
    api_url: str | None = None
    session_id: str = "default"

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest):
    reply, memory_saved = llm_client.chat(request.message, request.api_url, request.session_id)
    return {"reply": reply, "memory_saved": memory_saved}

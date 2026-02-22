from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Union
import os
import traceback
from llm_client import LLMClient
from logger import system_logger, chat_logger, settings_logger, redact_token

app = FastAPI(title="Assistant API")

@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        system_logger.error({
            "event_type": "unhandled_exception",
            "endpoint": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return JSONResponse(status_code=500, content={"error": "Internal Server Error", "message": str(e)})

llm_client = LLMClient()
ALLOWED_SETTINGS = {"memory_extraction_threshold"}

# Phase 7 Tokens
VALID_TOKENS = {
    "token-work": {
        "user_id": "user_1",
        "allowed_subjects": ["Work"],
        "role": "standard"
    },
    "token-admin": {
        "user_id": "admin_1",
        "allowed_subjects": ["*"],
        "role": "admin"
    }
}

class ChatRequest(BaseModel):
    message: str
    api_url: str | None = None
    session_id: str = "default"

class SettingUpdateRequest(BaseModel):
    key: str
    value: Union[str, float, int]

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest, http_request: Request, authorization: str | None = Header(default=None)):
    client_ip = http_request.client.host if http_request.client else "unknown"
    if not authorization or not authorization.startswith("Bearer "):
        chat_logger.warning({
            "event_type": "unauthorized_access",
            "endpoint": "/chat",
            "client_ip": client_ip,
            "session_id": request.session_id,
            "reason": "Missing or invalid authorization header format",
            "provided_token": redact_token(authorization)
        })
        return JSONResponse(
            status_code=401, 
            content={"error": "Unauthorized", "message": "Missing or invalid authentication token."}
        )
    
    auth_str = str(authorization)
    token = auth_str.split(" ")[1]
    if token not in VALID_TOKENS:
        chat_logger.warning({
            "event_type": "unauthorized_access",
            "endpoint": "/chat",
            "client_ip": client_ip,
            "session_id": request.session_id,
            "reason": "Invalid token",
            "provided_token": redact_token(token)
        })
        return JSONResponse(
            status_code=401, 
            content={"error": "Unauthorized", "message": "Missing or invalid authentication token."}
        )
        
    user = VALID_TOKENS[token]
    
    reply, memory_saved = llm_client.chat(
        request.message, 
        request.api_url, 
        request.session_id,
        user_id=user["user_id"],
        allowed_subjects=user["allowed_subjects"]
    )
    return {"reply": reply, "memory_saved": memory_saved}

@app.post("/admin/settings")
def update_setting(request: SettingUpdateRequest, http_request: Request, admin_token: str | None = Header(default=None)):
    client_ip = http_request.client.host if http_request.client else "unknown"
    expected_token = os.getenv("ADMIN_TOKEN")
    if not expected_token or admin_token != expected_token:
        settings_logger.warning({
            "event_type": "unauthorized_access",
            "endpoint": "/admin/settings",
            "client_ip": client_ip,
            "reason": "Invalid admin token",
            "provided_token": redact_token(admin_token)
        })
        raise HTTPException(status_code=403, detail="Forbidden")
        
    if request.key not in ALLOWED_SETTINGS:
        settings_logger.warning({
            "event_type": "invalid_setting_key",
            "endpoint": "/admin/settings",
            "client_ip": client_ip,
            "setting_key": request.key
        })
        raise HTTPException(status_code=400, detail=f"Invalid setting key. Allowed keys: {ALLOWED_SETTINGS}")
        
    from memory.db import MemoryDB
    db = MemoryDB(init_db=False)
    
    # Get old value for logging
    old_overrides = db.get_all_overrides()
    old_value = old_overrides.get(request.key, "default/unset")
    
    success = db.set_setting_override(request.key, str(request.value))
    if success:
        settings_logger.info({
            "event_type": "setting_updated",
            "setting_name": request.key,
            "old_value": old_value,
            "new_value": str(request.value),
            "changed_by": redact_token(admin_token) or "unknown",
            "status": "success",
            "client_ip": client_ip
        })
        return {"status": "success", "message": f"Updated {request.key}"}
        
    settings_logger.error({
        "event_type": "setting_update_failed",
        "setting_name": request.key,
        "attempted_value": str(request.value),
        "changed_by": redact_token(admin_token) or "unknown",
        "status": "failure",
        "client_ip": client_ip
    })
    raise HTTPException(status_code=500, detail="Failed to update setting")


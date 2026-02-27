import re
import json
import threading
import concurrent.futures
from datetime import datetime
from typing import Tuple, List, Optional
from collections import defaultdict
from urllib.parse import urlparse
from openai import OpenAI
from app.memory.manager import MemoryManager
from app.memory.db import MemoryDB
from app.logger import chat_logger, tool_logger, system_logger

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "172.17.72.151"}

def is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.hostname in ALLOWED_HOSTS and parsed.scheme in {"http", "https"}
    except Exception:
        return False

class LLMClient:
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.memory_db = MemoryDB()
        self.session_locks = defaultdict(threading.Lock)

    def _extract_memory_sync(self, message: str, url: str) -> dict | None:
        """
        Synchronous internal method to extract memory. Runs in strict mode.
        """
        system_prompt = (
            "You are a memory filter.\n"
            "Extract ONLY stable, factual, long-term user information.\n"
            "Examples:\n"
            "* Preferences\n"
            "* Allergies\n"
            "* Goals\n"
            "* Projects\n"
            "* Identity facts\n\n"
            "Do NOT extract:\n"
            "* Temporary emotions\n"
            "* One-time events\n"
            "* Casual remarks\n"
            "* Questions\n\n"
            "If no valid memory exists, respond with exactly: NONE\n"
            "Otherwise respond with ONLY a valid JSON object in this format:\n"
            "{\n"
            '  "content": "The extracted factual memory sentence.",\n'
            '  "subject": "A short category (e.g. Work, Health, Personal, Tech)",\n'
            '  "importance": 3\n'
            "}\n"
            "Importance should be an integer from 1 to 5, where 1 = trivial, 3 = normal, 5 = critical."
        )
        try:
            client = OpenAI(base_url=url, api_key="lm-studio", timeout=5.0)
            response = client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.0,
            )
            raw_content = response.choices[0].message.content.strip()
            # Clean up reasoning if present
            cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
            
            if cleaned_content.upper() == "NONE" or not cleaned_content:
                return None
                
            # Find JSON payload in case LLM wraps it in markdown blocks
            if "```json" in cleaned_content:
                start = cleaned_content.find("```json") + 7
                end = cleaned_content.rfind("```")
                cleaned_content = cleaned_content[start:end].strip()
            elif "```" in cleaned_content:
                start = cleaned_content.find("```") + 3
                end = cleaned_content.rfind("```")
                cleaned_content = cleaned_content[start:end].strip()
                
            try:
                parsed = json.loads(cleaned_content)
                
                content = parsed.get("content")
                subject = parsed.get("subject")
                
                # Defend against LLM hallucinating lists/dicts for fields
                if isinstance(content, list):
                    content = " ".join(str(x) for x in content)
                elif isinstance(content, dict):
                    content = str(content)
                    
                if isinstance(subject, list):
                    subject = str(subject[0]) if subject else "General"
                elif isinstance(subject, dict):
                    subject = "General"
                
                if not content or not subject:
                    system_logger.warning({"event_type": "memory_extraction_validation_failed", "parsed": parsed})
                    return None
                    
                raw_importance = parsed.get("importance", 3)
                try:
                    # Defend against "importance": "high"
                    if isinstance(raw_importance, str) and not raw_importance.isdigit():
                        importance = 5 if "high" in raw_importance.lower() else (1 if "low" in raw_importance.lower() else 3)
                    else:
                        importance = int(raw_importance)
                    importance = max(1, min(5, importance))
                except (ValueError, TypeError):
                    importance = 3
                    
                return {
                    "content": str(content).strip(),
                    "subject": str(subject).strip(),
                    "importance": importance
                }
            except json.JSONDecodeError as e:
                system_logger.error({"event_type": "memory_extraction_json_parse_failed", "error": str(e), "raw": cleaned_content}, exc_info=True)
                return None
        except Exception as e:
            system_logger.error({"event_type": "memory_extraction_failed", "error": str(e)}, exc_info=True)
            return None

    def chat(self, message: str, api_url: str | None = None, session_id: str = "default", user_id: str = "default_user", allowed_subjects: Optional[List[str]] = None) -> Tuple[str, bool]:
        if allowed_subjects is None:
            allowed_subjects = ["*"]
            
        # Default url if none provided
        url = api_url if api_url else "http://127.0.0.1:1234/v1"
        
        if not is_allowed_url(url):
            return "Error: The provided API URL is not in the allowed hosts list.", False
            
        chat_logger.info({
            "event_type": "chat_request",
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "allowed_subjects": allowed_subjects
        })
        
        memory_saved = False

        # Run memory extraction in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future_memory = executor.submit(lambda m=message, u=url: self._extract_memory_sync(m, u))

            cleaned_content = ""
            with self.session_locks[session_id]:
                try:
                    # 1. Load history & Prune to max_chat_history - 1
                    history = self.memory_manager.load(session_id)
                    history = self.memory_manager.prune(history, reserve=1)
                    
                    # 2. Append new user message
                    history.append({"role": "user", "content": message})
                    
                    # 3. Retrieve recent database memories for injection
                    recent_memories = self.memory_db.retrieve_recent_memories(session_id, user_id=user_id, allowed_subjects=allowed_subjects, limit=5)
                    
                    system_prompt_parts = [
                        "You are a helpful AI assistant. You always fulfill the user's requests to the best of your ability.",
                        "RULES:",
                        "- Be concise and factual.",
                        "- NEVER hallucinate events, emotions, or actions that are not explicitly stated in your memory."
                    ]
                    
                    today = datetime.now().strftime("%Y-%m-%d")
                    daily_events = self.memory_db.get_daily_aggregation(session_id, today, user_id=user_id, allowed_subjects=allowed_subjects, min_importance=3)
                    
                    if daily_events:
                        events_text_parts = []
                        for subj, events in daily_events.items():
                            events_text_parts.append(f"- {subj}:")
                            for event in events:
                                events_text_parts.append(f"   • {event['content']}")
                        events_text = "\n".join(events_text_parts)
                    else:
                        events_text = "No significant events recorded today."
                        
                    system_prompt_parts.append(
                        f"\nToday's Important Events:\n{events_text}\n\n"
                        "CONSTRAINT: Only use the above facts when answering questions about today. Do not fabricate additional events. If asked about something not listed, state clearly that you have no record of it."
                    )
                    
                    if recent_memories:
                        memory_text = "\n".join([f"- {m}" for m in recent_memories])
                        system_prompt_parts.append(
                            f"\nGeneral User Known Facts (from previous sessions):\n{memory_text}\n\n"
                            "Use these facts when relevant. Do not mention them unless needed."
                        )
                    
                    system_prompt = "\n".join(system_prompt_parts)
                    messages = [{"role": "system", "content": system_prompt}] + history
                    
                    # 4. Call Model
                    import time
                    start_time = time.time()
                    client = OpenAI(base_url=url, api_key="lm-studio", timeout=10.0)
                    response = client.chat.completions.create(
                        model="local-model",
                        messages=messages,
                        temperature=0.7,
                    )
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    response_message = response.choices[0].message
                    raw_content = response_message.content or ""
                    
                    if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                        for tool_call in response_message.tool_calls:
                            try:
                                args_parsed = json.loads(tool_call.function.arguments)
                                args_summary = {
                                    "fields": list(args_parsed.keys()),
                                    "content_length": len(tool_call.function.arguments)
                                }
                            except Exception:
                                args_summary = {"content_length": len(tool_call.function.arguments), "parse_error": True}
                                
                            tool_name = tool_call.function.name
                            # Check for system settings tool
                            if tool_name == "update_setting":
                                from app.settings import get_settings_schema
                                import inspect
                                # Parse args into kwargs
                                # (Assuming this is where the logic for update_setting would go)
                            
                            tool_logger.info({
                                "event_type": "tool_call",
                                "status": "success",
                                "session_id": session_id,
                                "user_id": user_id,
                                "tool_name": tool_call.function.name,
                                "arguments_summary": args_summary
                            })
                    
                    # 5. Strip reasoning
                    cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
                    
                    chat_logger.info({
                        "event_type": "chat_response",
                        "status": "success",
                        "session_id": session_id,
                        "user_id": user_id,
                        "reply_length": len(cleaned_content),
                        "had_tool_calls": bool(getattr(response_message, "tool_calls", False)),
                        "duration_ms": duration_ms
                    })
                    
                    # 6. Append assistant reply
                    history.append({"role": "assistant", "content": cleaned_content})
                    
                    # 7. Prune again and Save
                    history = self.memory_manager.prune(history)
                    self.memory_manager.save(session_id, history)
                    
                except Exception as e:
                    chat_logger.error({
                        "event_type": "chat_failed",
                        "status": "failure",
                        "session_id": session_id,
                        "user_id": user_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    })
                    return f"Error connecting to LM Studio at {url}: {str(e)}", False

            # Wait for memory extraction to finish now that main loop is done
            try:
                extracted_memory = future_memory.result(timeout=2.0)
                if extracted_memory:
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    from app.settings import load_settings
                    settings = load_settings(db=self.memory_db)
                    threshold = settings.get("memory_extraction_threshold", 0.6)
                    
                    try:
                        threshold = max(0.0, min(1.0, float(threshold)))
                    except (ValueError, TypeError):
                        threshold = 0.6
                        
                    normalized_importance = extracted_memory["importance"] / 5.0
                    
                    if normalized_importance >= threshold:
                        mem_id = self.memory_db.store_memory(
                            session_id=session_id,
                            content=extracted_memory["content"],
                            memory_date=today,
                            subject=extracted_memory["subject"],
                            importance=extracted_memory["importance"],
                            user_id=user_id,
                            access_mode="private"
                        )
                        memory_saved = mem_id is not None
                    else:
                        print(f"[Memory Skipped] importance={extracted_memory['importance']} normalized={normalized_importance} threshold={threshold}")

            except Exception as e:
                system_logger.error({"event_type": "memory_processing_error", "error": str(e)}, exc_info=True)
                
            return cleaned_content, memory_saved

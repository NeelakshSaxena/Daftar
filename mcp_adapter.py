from mcp.server.fastmcp import FastMCP
import logging

# Ensure absolute imports work when mcp_adapter.py is run directly
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from app.memory.db import MemoryDB
from app.memory.manager import MemoryManager
from app.settings import load_settings
from app.tools.files import FilesTool
from app.tools.memory import MemoryTool
from app.logger import tool_logger

# Create MCP server instance
mcp = FastMCP("LocalMCPAdapter")

# Initialize single stateless instance for thin adapter logic
# Explicitly set base_dir to a dedicated workspace directory
# so LM Studio cannot read the MCP server code files.
base_dir = Path(__file__).parent.resolve() / "workspace"
base_dir.mkdir(exist_ok=True)
files_tool = FilesTool(base_dir=base_dir)

# Initialize memory layer dependencies
memory_db = MemoryDB(init_db=True)
memory_tool = MemoryTool(db_instance=memory_db)


@mcp.tool()
def ping() -> str:
    """
    Simple connectivity test tool.
    Returns 'pong' when called.
    """
    return "pong"

@mcp.tool()
def get_current_time() -> str:
    """
    Get the current system date and time.
    Use this to find out what day it is before saving memories or answering time-sensitive questions.
    """
    from datetime import datetime
    return datetime.now().strftime("%I:%M %p, %A, %B %d, %Y (%Y-%m-%d)")

@mcp.tool()
def read_file(path: str) -> str:
    """
    Read a file from disk, returning its contents as a string.
    Path must be relative to the project root. Do not include leading slashes or drive letters.
    """
    tool_logger.info({
        "event_type": "mcp_adapter_tool_call",
        "tool_name": "read_file",
        "path": path,
    })
    return files_tool.read_file(path)

@mcp.tool()
def store_memory(content: str, memory_date: str, subject: str, importance: int) -> dict:
    """
    USE THIS TOOL PROACTIVELY to store a new memory into the DB whenever the user shares a fact, preference, allergy, or long-term information about themselves.
    - content: The core factual or relevant information to retain.
    - memory_date: Formatted as YYYY-MM-DD.
    - subject: The canonical subject matter (e.g. "Work", "Health", "Preferences").
    - importance: Integer from 1 to 5 indicating significance. Must meet threshold to be saved.
    Returns highly structured JSON indicating success or explicit rejection reason.
    """
    return memory_tool.store_memory(
        content=content,
        memory_date=memory_date,
        subject=subject,
        importance=importance,
        session_id="default_mcp_session",
        user_id="default_user",
        access_mode="private"
    )



@mcp.tool()
def retrieve_memory(query: str = "", scope: list[str] = None, state_filter: str = "active", limit: int = 5) -> dict:
    """
    Retrieve facts, preferences, and long-term context about the user.
    - query: Optional string to match within memories (e.g. "Python").
    - scope: Optional list of subjects to narrow the search (e.g. ["Preferences", "Work"]). If omitted, searches all allowed.
    - state_filter: Lifecycle state to filter by. Defaults to "active". Do not request "superseded" unless specifically auditing old versions.
    - limit: Maximum number of results to retrieve (default 5, max 20).
    Returns a dictionary containing a 'results' array, deterministically ranked by source priority, confidence, and recency.
    """
    return memory_tool.retrieve_memory(
        query=query,
        scope=scope,
        state_filter=state_filter,
        limit=limit,
        user_id="default_user"  # Strict isolation required by contract
    )

if __name__ == "__main__":
    # Verify backend dependencies load correctly
    # We already initialized MemoryDB globally, so it's ready.
    
    # Run over stdio so LM Studio can communicate with it
    mcp.run()

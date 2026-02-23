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
from app.logger import tool_logger

# Create MCP server instance
mcp = FastMCP("LocalMCPAdapter")

# Initialize single stateless instance for thin adapter logic
# Explicitly set base_dir to the adapter's directory so it works correctly
# when LM Studio launches it from a different working directory.
adapter_dir = Path(__file__).parent.resolve()
files_tool = FilesTool(base_dir=adapter_dir)

@mcp.tool()
def ping() -> str:
    """
    Simple connectivity test tool.
    Returns 'pong' when called.
    """
    return "pong"

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

if __name__ == "__main__":
    # Verify backend dependencies load correctly by testing DB init
    # We do a basic check here just to ensure imports are fully viable
    db = MemoryDB(init_db=False)
    
    # Run over stdio so LM Studio can communicate with it
    mcp.run()

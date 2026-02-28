# 🧠 Daftar v1.0.0 (Initial Release)

Daftar is a production-grade, multi-tenant memory engine and Local Model Context Protocol (MCP) server that empowers LLMs with persistent, long-term memory.

## ✨ Key Features
- **Persistent Memory**: Save and recall facts, preferences, and context with ease.
- **MCP Integration**: Fully compatible with the Model Context Protocol (LM Studio, Claude Desktop).
- **Web UI & REST API**: Includes a Flask Memory Viewer and a FastAPI backend.
- **Secure Storage**: Multi-tenant, concurrency-safe SQLite architecture with attribute-based access control.

## 📦 What's Changed
- Initial v1.0.0 release of Daftar Engine! 🚀
- Full MCP adapter implementation for [store_memory](file:///g:/Projects/MCPs/Daftar/mcp_adapter.py#61-80), [retrieve_memory](file:///g:/Projects/MCPs/Daftar/mcp_adapter.py#83-100), [read_file](file:///g:/Projects/MCPs/Daftar/mcp_adapter.py#48-60), and more.
- Comprehensive local web UI ([app/web.py](file:///g:/Projects/MCPs/Daftar/app/web.py)) for viewing active user memories.
- Hardened database schemas mapped for path traversal and locking safety.
- Stress-tested concurrency tests and payload validation logic included.

## 🚀 Getting Started
Please see the [README.md](https://github.com/NeelakshSaxena/Daftar/blob/main/README.md) for full installation and usage instructions.

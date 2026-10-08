"""
MCP client configuration for the 7-server setup.

Defines how to launch each MCP server as a stdio subprocess. This dict is
consumed by `langchain_mcp_adapters.client.MultiServerMCPClient` inside
`agents/orchestrator.py::build_agent_mcp()`.

Servers:
  1. auckland-hospital-crm      — custom Python server, wraps CRMTool (5 tools)
  2. auckland-hospital-memory   — custom Python server, wraps 4-tier memory (6 tools)
  3. auckland-hospital-kb       — custom Python server, wraps RAGTool (3 tools)
  4. auckland-hospital-web      — custom Python server, wraps WebSearchTool (1 tool)
  5. auckland-hospital-cag      — custom Python server, wraps CAGCache (4 tools)
  6. auckland-hospital-crawler  — custom Python server, wraps AucklandHospitalWebCrawler
                         (1 async tool)
  7. postgres          — off-the-shelf @modelcontextprotocol/server-postgres,
                         pointed at Supabase (zero custom code)

Requires:
  - `mcp` and `langchain-mcp-adapters` installed via requirements.txt
  - Node.js + npx available on PATH (for the postgres server)
  - SUPABASE_POSTGRES_URL in .env (or falls back to DATABASE_URL)
"""

import os
import sys

# Absolute path to src/ so the subprocess launches regardless of cwd
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYTHON = sys.executable  # current interpreter (venv-aware)


def build_mcp_server_config() -> dict:
    """
    Returns a dict suitable for MultiServerMCPClient.

    All 6 custom servers are always included.
    The postgres server is only included if a connection string is
    present in the environment, so the application can start without it.
    """
    config = {
        "auckland-hospital-crm": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.crm_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
        "auckland-hospital-memory": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.memory_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
        "auckland-hospital-kb": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.rag_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
        "auckland-hospital-web": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.web_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
        "auckland-hospital-cag": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.cag_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
        "auckland-hospital-crawler": {
            "command": _PYTHON,
            "args": ["-m", "mcp_servers.crawler_server"],
            "transport": "stdio",
            "cwd": _SRC_DIR,
        },
    }

    pg_url = os.getenv("SUPABASE_POSTGRES_URL") or os.getenv("DATABASE_URL")
    if pg_url:
        config["postgres"] = {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-postgres",
                pg_url,
            ],
            "transport": "stdio",
        }

    return config

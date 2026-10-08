"""Smoke-check the MCP-backed agent across CRM, memory, knowledge, web, and optional PostgreSQL services."""

import asyncio
import os
import sys

# Ensure src/ is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
load_dotenv()

from loguru import logger


async def main() -> None:
    from agents.orchestrator import build_agent_mcp

    print("=" * 70)
    print(" MCP integration check")
    print("=" * 70)

    print("\n[1/3] Building MCP-backed agent (all tools via MCP)...")
    agent = await build_agent_mcp()

    print(f"\n[2/3] MCP tools discovered ({len(agent.mcp_tools)} total):")
    for name, tool in agent.mcp_tools.items():
        desc = (tool.description or "").strip().split("\n")[0][:70]
        print(f"   - {name:25s}  {desc}")

    print("\n[3/3] Running multi-turn conversation...")
    user_id = "64211030736"
    session_id = "mcp-full-test"

    turns = [
        # direct route
        ("Hi, I'm Aroha. My mobile is 021 103 0736.", "direct"),
        # CRM route → lookup_patient via MCP
        ("Can you look up my patient record?", "crm"),
        # CRM route → search_doctors via MCP
        ("What cardiologists do you have available?", "crm"),
        # RAG route → search_hospital_kb via MCP
        ("What cardiac services does the hospital offer?", "rag"),
        # Web route → web_search via MCP
        ("What are the current visiting hours at Auckland Hospital?", "web_search"),
    ]

    for i, (msg, expected_route) in enumerate(turns, 1):
        print(f"\n{'─' * 70}")
        print(f"Turn {i}: {msg}")
        print(f"Expected route: {expected_route}")
        print("─" * 70)
        resp = await agent.achat(msg, user_id=user_id, session_id=session_id)
        actual = resp.routes[0] if resp.routes else resp.route
        match = "Y" if actual == expected_route else "X"
        print(f"  Route   : {actual} [{match}]")
        print(f"  Latency : {resp.latency_ms}ms")
        print(f"  Answer  : {resp.answer[:300]}")

    print(f"\n{'=' * 70}")
    print(" MCP integration check complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

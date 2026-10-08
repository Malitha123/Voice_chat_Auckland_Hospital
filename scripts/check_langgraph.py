"""
Integration smoke test for the LangGraph multi-agent system.

Covers graph rendering, multi-turn routing across specialised agents,
and selective memory persistence.
"""

import os
import sys
from loguru import logger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agents.orchestrator import build_agent
from infrastructure.log import setup_logging

def run_smoke_check():
    setup_logging("INFO")
    
    # Build the multi-agent orchestrator.
    logger.info("Initializing LangGraph Multi-Agent System...")
    agent = build_agent()
    
    # Render the graph for topology inspection.
    print("\n" + "="*80)
    print("🧠 LANGGRAPH ARCHITECTURE (MERMAID)")
    print("="*80)
    try:
        print(agent.graph.get_graph(xray=True).draw_mermaid())
    except Exception as e:
        logger.warning(f"Could not visualize graph: {e}")
    print("="*80 + "\n")

    # Run a multi-turn integration scenario.
    user_id = "smoke_user_w08"
    session_id = "session_langgraph_001"
    
    turns = [
        # Direct route: greeting
        "Hi! I'm David. Just arrived at Auckland Hospital for my checkup.",
        
        # Clinical route: patient history / RAG
        "I've been feeling some chest tightness lately. What are the common protocols for triage here?",
        
        # Clinical route: memory persistence
        "Oh, and I'm allergic to Penicillin. Please remember that.",
        
        # Administrative route: doctor search
        "Who is the best cardiologist available tonight for a consultation?",
        
        # Administrative route: appointment request
        "Can you book a slot with Dr. Tharindu for tomorrow morning?",
        
        # Clinical route: selective memory recall
        "Wait, based on my allergy I mentioned earlier, are there any specific meds I should avoid if they admit me?",
        
        # Direct route: closing turn
        "Thanks for the help! I'll head to the OPD now."
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[Turn {i}] User: {msg}")
        resp = agent.chat(msg, user_id, session_id)
        
        print(f"--- [REPLY] Route: {resp.route} | Latency: {resp.latency_ms}ms ---")
        print(f"Assistant: {resp.answer}")
        
    logger.success("Multi-turn LangGraph integration scenario completed")

if __name__ == "__main__":
    run_smoke_check()

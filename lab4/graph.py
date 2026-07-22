# =============================================================
# graph.py — LangGraph Supervisor Pattern for AI Security Platform
# =============================================================

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from agents import (
    behavior_monitor,
    llm_hardener,
    safe_executor,
    security_auditor,
    security_gate,
    security_logger,
    supervisor_agent,
)
from state import SecurityState


# ─────────────────────────────────────────────────────────────
# Routing function
# ─────────────────────────────────────────────────────────────

def route_from_supervisor(state: SecurityState) -> str:
    """Maps next_agent from supervisor state to a graph node or END."""
    next_agent = state.get("next_agent", "security_gate")
    if next_agent == "FINISH":
        return END
    return next_agent


# ─────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────

def build_graph():
    """
    Builds and compiles the LangGraph security pipeline.

    Topology:
        supervisor ─── conditional ──► security_gate
                                   ──► llm_hardener
                                   ──► safe_executor
                                   ──► behavior_monitor
                                   ──► security_logger
                                   ──► security_auditor
                                   ──► END

        All specialist nodes return to supervisor.
    """
    graph = StateGraph(SecurityState)

    # Register nodes
    graph.add_node("supervisor",       supervisor_agent)
    graph.add_node("security_gate",    security_gate)
    graph.add_node("llm_hardener",     llm_hardener)
    graph.add_node("safe_executor",    safe_executor)
    graph.add_node("behavior_monitor", behavior_monitor)
    graph.add_node("security_logger",  security_logger)
    graph.add_node("security_auditor", security_auditor)

    # Entry point
    graph.set_entry_point("supervisor")

    # Supervisor routes conditionally
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "security_gate":    "security_gate",
            "llm_hardener":     "llm_hardener",
            "safe_executor":    "safe_executor",
            "behavior_monitor": "behavior_monitor",
            "security_logger":  "security_logger",
            "security_auditor": "security_auditor",
            END:                END,
        },
    )

    # All specialists loop back to supervisor
    for node in [
        "security_gate",
        "llm_hardener",
        "safe_executor",
        "behavior_monitor",
        "security_logger",
        "security_auditor",
    ]:
        graph.add_edge(node, "supervisor")

    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)

# =============================================================
# graph.py — Multi-Agent Supervisor Graph
# =============================================================
# Key difference from Lab 2:
#   - ALL agents return to the Supervisor after finishing.
#   - The Supervisor is an active node (not just a router function).
#   - Conditional edges come FROM the Supervisor, not from evaluate.
#   - This is the standard LangGraph Supervisor pattern.
#
# Flow:
#   START → supervisor
#   supervisor → research | memory | analysis | evaluation |
#                improve  | report | audit    | END
#   every agent → supervisor  (after completing their task)
# =============================================================

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents import (
    analysis_agent,
    audit_agent,
    evaluation_agent,
    improve_agent,
    memory_agent,
    report_agent,
    research_agent,
    supervisor_agent,
)
from state import MultiAgentState


# ─────────────────────────────────────────────────────────────
# Supervisor Router
# ─────────────────────────────────────────────────────────────

def route_from_supervisor(state: MultiAgentState) -> str:
    """
    Reads state['next_agent'] set by supervisor_agent and returns
    the corresponding node name for LangGraph to route to.
    Maps 'FINISH' to the LangGraph END sentinel.
    """
    next_agent = state.get("next_agent", "research")
    if next_agent == "FINISH":
        return END
    return next_agent


# ─────────────────────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────────────────────

def build_graph():
    """
    Builds and compiles the Multi-Agent Research System graph.

    Architecture (Supervisor Pattern):
    ────────────────────────────────────────────────────────────
                        ┌──────────────┐
              ┌────────►│  Supervisor  │◄────────────────┐
              │         └──────┬───────┘                 │
              │                │ routes to               │
              │   ┌────────────┼────────────────────┐    │
              │   ▼            ▼                    ▼    │
           research         memory              analysis  │
              │               │                    │      │
              └───────────────┴────────────────────┘      │
                              │ (all → supervisor)        │
                              │                           │
                    evaluation │  improve │ report │ audit │
                              └──────────────────────────-┘
                                             │
                                   supervisor → FINISH → END
    """
    workflow = StateGraph(MultiAgentState)

    # ── Register nodes ───────────────────────────────────────
    workflow.add_node("supervisor",  supervisor_agent)
    workflow.add_node("research",    research_agent)
    workflow.add_node("memory",      memory_agent)
    workflow.add_node("analysis",    analysis_agent)
    workflow.add_node("evaluation",  evaluation_agent)
    workflow.add_node("improve",     improve_agent)
    workflow.add_node("report",      report_agent)
    workflow.add_node("audit",       audit_agent)

    # ── Entry point ──────────────────────────────────────────
    workflow.add_edge(START, "supervisor")

    # ── Supervisor routes to any agent ───────────────────────
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "research":   "research",
            "memory":     "memory",
            "analysis":   "analysis",
            "evaluation": "evaluation",
            "improve":    "improve",
            "report":     "report",
            "audit":      "audit",
            END:          END,
        },
    )

    # ── Every agent returns to supervisor ────────────────────
    for agent in ["research", "memory", "analysis",
                  "evaluation", "improve", "report", "audit"]:
        workflow.add_edge(agent, "supervisor")

    # ── Compile with checkpointing ───────────────────────────
    app = workflow.compile(checkpointer=InMemorySaver())

    # ── Export graph.png ─────────────────────────────────────
    _save_graph_image(app)

    return app


# ─────────────────────────────────────────────────────────────
# Graph Image Export
# ─────────────────────────────────────────────────────────────

def _save_graph_image(app) -> None:
    """Exports the compiled graph as graph.png via Mermaid rendering."""
    try:
        import os
        from tools import LAB3_DIR
        image_bytes = app.get_graph().draw_mermaid_png()
        path = os.path.join(LAB3_DIR, "graph.png")
        with open(path, "wb") as f:
            f.write(image_bytes)
        print(f"[Graph] Diagram exported → {path}")
    except Exception as exc:
        print(f"[Graph] graph.png export skipped: {exc}")

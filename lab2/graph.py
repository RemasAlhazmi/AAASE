# =============================================================
# graph.py
# LangGraph workflow definition, routing logic, and graph export.
# =============================================================

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from nodes import (
    analyze_node,
    audit_node,
    collect_node,
    evaluate_node,
    improve_node,
    planner_node,
    report_node,
    store_memory_node,
)
from state import AgentState

# ─────────────────────────────────────────────────────────────
# Quality Router
# ─────────────────────────────────────────────────────────────

MAX_RETRIES = 2


def quality_router(state: AgentState) -> str:
    """
    Decides what to do after evaluation.

    Logic:
        - score >= 7                       → proceed to "report"
        - score < 7  AND retry_count > MAX_RETRIES  → proceed to "report" (exhausted)
        - score < 7  AND retry_count <= MAX_RETRIES → go to "improve" for another cycle

    Note: evaluate_node pre-increments retry_count when score < 7, so the
    comparison here reflects retries that *have already been scheduled*.
    """
    score = state.get("quality_score", 0)
    retry_count = state.get("retry_count", 0)

    if score >= 7:
        print(f"\n[Router] Score {score}/10 ≥ 7 — quality accepted. → report")
        return "report"

    if retry_count > MAX_RETRIES:
        print(
            f"\n[Router] Score {score}/10 < 7 but max retries ({MAX_RETRIES}) "
            "exhausted. → report"
        )
        return "report"

    print(
        f"\n[Router] Score {score}/10 < 7 — triggering retry "
        f"#{retry_count}/{MAX_RETRIES}. → improve"
    )
    return "improve"


# ─────────────────────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────────────────────

def build_graph():
    """
    Constructs and compiles the AI Tool Research Agent graph.

    Workflow
    --------
    START
      └─► planner ──► collect ──► store_memory ──► analyze ──► evaluate
                         ▲                                          │
                         │          score < 7 & retries ≤ 2        │
                         │◄──────────── improve ◄───────────────────┤
                                                                    │
                                       score ≥ 7  OR retries > 2   │
                                                                    ▼
                                                        report ──► audit ──► END

    Notes
    -----
    - InMemorySaver enables per-thread state checkpointing.
    - graph.png is exported via Mermaid after compilation.
    """
    workflow = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────
    workflow.add_node("planner",      planner_node)
    workflow.add_node("collect",      collect_node)
    workflow.add_node("store_memory", store_memory_node)
    workflow.add_node("analyze",      analyze_node)
    workflow.add_node("evaluate",     evaluate_node)
    workflow.add_node("improve",      improve_node)
    workflow.add_node("report",       report_node)
    workflow.add_node("audit",        audit_node)

    # ── Static edges (happy path) ────────────────────────────
    workflow.add_edge(START,          "planner")
    workflow.add_edge("planner",      "collect")
    workflow.add_edge("collect",      "store_memory")
    workflow.add_edge("store_memory", "analyze")
    workflow.add_edge("analyze",      "evaluate")

    # ── Conditional edge after evaluation ────────────────────
    workflow.add_conditional_edges(
        "evaluate",
        quality_router,
        {
            "improve": "improve",   # retry loop
            "report":  "report",    # finalize
        },
    )

    # ── Retry loop: improved queries → re-collect onward ─────
    workflow.add_edge("improve", "collect")

    # ── Finalization path ────────────────────────────────────
    workflow.add_edge("report", "audit")
    workflow.add_edge("audit",  END)

    # ── Compile with in-memory checkpointing ─────────────────
    app = workflow.compile(checkpointer=InMemorySaver())

    # ── Export graph diagram ─────────────────────────────────
    _save_graph_image(app)

    return app


# ─────────────────────────────────────────────────────────────
# Graph Image Export
# ─────────────────────────────────────────────────────────────

def _save_graph_image(app) -> None:
    """
    Renders the compiled graph as a PNG file using Mermaid.
    Saved to graph.png in the current working directory.
    Silently skips if the optional rendering dependency is unavailable.
    """
    try:
        image_bytes = app.get_graph().draw_mermaid_png()
        output_path = "graph.png"
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        print(f"[Graph] Diagram exported → {output_path}")
    except Exception as exc:
        print(f"[Graph] graph.png export skipped: {exc}")

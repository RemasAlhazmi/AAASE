# =============================================================
# main.py — CLI entry point (for testing without the UI)
# =============================================================

from dotenv import load_dotenv
from graph import build_graph

load_dotenv()


def main() -> None:
    print("\n" + "=" * 60)
    print("   MULTI-AGENT AI RESEARCH SYSTEM — Lab 3".center(60))
    print("   Powered by LangGraph Supervisor Pattern".center(60))
    print("=" * 60)

    app = build_graph()

    tool = input("\nEnter AI tool name (e.g. LangGraph, CrewAI): ").strip()
    if not tool:
        print("[Error] No tool name provided.")
        return

    initial_state = {
        "tool_name":           tool,
        "current_agent":       "",
        "next_agent":          "",
        "research_plan":       "",
        "search_queries":      [],
        "sources":             [],
        "memory_stored":       False,
        "analysis":            "",
        "quality_score":       0,
        "missing_information": "",
        "quality_feedback":    "",
        "retry_count":         0,
        "final_report":        "",
        "audit_result":        "",
        "execution_logs":      [],
    }

    config = {"configurable": {"thread_id": f"lab3-{tool.lower().replace(' ', '-')}"}}

    print(f"\n[System] Starting multi-agent research for: {tool}\n")

    final_state = None
    for snapshot in app.stream(initial_state, config, stream_mode="values"):
        final_state = snapshot

    if not final_state:
        print("[Error] No output produced.")
        return

    width = 60
    print("\n" + "=" * width)
    print("  FINAL REPORT")
    print("=" * width)
    print(final_state.get("final_report", "No report generated."))

    print("\n" + "=" * width)
    print("  AUDIT")
    print("=" * width)
    print(final_state.get("audit_result", ""))

    print("\n" + "=" * width)
    print("  EXECUTION LOG")
    print("=" * width)
    for entry in final_state.get("execution_logs", []):
        print(entry)


if __name__ == "__main__":
    main()

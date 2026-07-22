# Entry point for the AI Tool Research Agent.


from dotenv import load_dotenv

from graph import build_graph

# Load environment variables from .env
load_dotenv()


# Main 1.0


def main() -> None:
    """
    Runs the AI Tool Research Agent interactively.

    Steps
    -----
    1. Build and compile the LangGraph workflow (also exports graph.png).
    2. Prompt the user for an AI tool name.
    3. Stream the graph execution, printing node-level progress in real time.
    4. Display the final report, audit record, and full execution log.

    Example tools
    -------------
    LangGraph, LangChain, CrewAI, AutoGen, Ollama, OpenRouter,
    Hugging Face, ChromaDB, Pinecone, n8n
    """
    _print_banner()

    # ── Build graph 2.0
    app = build_graph()


    tool = input(
        "\nEnter AI tool name (e.g. LangGraph, CrewAI, Ollama): "
    ).strip()

    if not tool:
        print("[Error] No tool name provided. Exiting.")
        return


    initial_state = {
        "tool_name":           tool,
        "research_plan":       "",
        "search_queries":      [],
        "sources":             [],
        "analysis":            "",
        "quality_score":       0,
        "missing_information": "",   # populated by evaluate_node; used by improve_node
        "retry_count":         0,
        "final_report":        "",
        "audit_result":        "",
        "execution_logs":      [],
    }

    # Thread ID enables per-run checkpointing via InMemorySaver
    config = {
        "configurable": {
            "thread_id": f"research-{tool.lower().replace(' ', '-')}"
        }
    }

    print(f"\n[Agent] Starting research for: {tool}\n")

    # ── Stream execution
    # stream_mode="values" yields the full state after every node step
    final_state = None
    for snapshot in app.stream(initial_state, config, stream_mode="values"):
        final_state = snapshot   # keep latest full-state snapshot

    if final_state is None:
        print("[Error] Agent produced no output. Check your API keys and .env.")
        return

    #  Final report
    _section_header("FINAL REPORT")
    print(final_state.get("final_report", "No report was generated."))

    #  Audit record
    _section_header("AUDIT RECORD")
    print(final_state.get("audit_result", "No audit record available."))

    # ── Execution log
    _section_header("EXECUTION LOG")
    for entry in final_state.get("execution_logs", []):
        print(entry)

    print("\n[Agent] Research complete.\n")



# Helpers


def _print_banner() -> None:
    """Prints the application header banner."""
    width = 60
    print("\n" + "=" * width)
    print("         AI TOOL RESEARCH AGENT".center(width))
    print("   Powered by LangGraph + Gemini".center(width))
    print("=" * width)


def _section_header(title: str) -> None:
    """Prints a formatted section separator."""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)



# Entry point


if __name__ == "__main__":
    main()

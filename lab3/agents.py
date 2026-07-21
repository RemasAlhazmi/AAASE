# =============================================================
# agents.py — All specialized agents + Supervisor
# =============================================================
# Key difference from Lab 2:
#   - Each agent has a SYSTEM PROMPT defining its identity.
#   - Every agent sets current_agent so the Supervisor knows
#     who just finished.
#   - The Supervisor reads state and DECIDES the next agent —
#     it is not a hardcoded conditional edge function.
#   - Agents are truly independent: each has its own LLM call
#     with its own system prompt. They share state but not logic.
# =============================================================

import json
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from prompts import (
    ANALYSIS_PROMPT,
    EVALUATION_PROMPT,
    IMPROVE_PROMPT,
    PLANNER_PROMPT,
    QUERY_EXTRACTION_PROMPT,
    REPORT_PROMPT,
    RESEARCH_AGENT_SYSTEM,
    MEMORY_AGENT_SYSTEM,
    ANALYSIS_AGENT_SYSTEM,
    EVALUATION_AGENT_SYSTEM,
    IMPROVE_AGENT_SYSTEM,
    REPORT_AGENT_SYSTEM,
    AUDIT_AGENT_SYSTEM,
    SUPERVISOR_SYSTEM,
)
from state import MultiAgentState, QualityEvaluation
from tools import (
    MAX_RESEARCH_CHARS,
    build_keyword_queries,
    build_references,
    get_llm,
    get_vector_store,
    log,
    save_audit,
    save_report,
    tavily_search,
)

from datetime import datetime

# ─────────────────────────────────────────────────────────────
# Helper: parse JSON list from LLM response
# ─────────────────────────────────────────────────────────────

def _parse_json_list(raw: str, fallback: list[str]) -> list[str]:
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    try:
        result = json.loads(match.group()) if match else []
        if isinstance(result, list) and len(result) > 0:
            return result
    except Exception:
        pass
    return fallback


# =============================================================
# SUPERVISOR AGENT
# =============================================================

def supervisor_agent(state: MultiAgentState) -> dict:
    """
    The orchestrator of the multi-agent pipeline.

    Reads the current state and decides which agent to activate next
    using clear decision rules. Logs its reasoning at every step.

    Routing logic:
        no sources          → research
        sources, no memory  → memory
        memory, no analysis → analysis
        analysis, no score  → evaluation
        score < 7, retries < 2 → improve
        score >= 7 OR retries >= 2 → report
        report done         → audit
        audit done          → FINISH
    """
    print("\n" + "=" * 55)
    print("[SUPERVISOR] Evaluating pipeline state...")

    sources       = state.get("sources") or []
    memory_stored = state.get("memory_stored", False)
    analysis      = state.get("analysis", "")
    quality_score = state.get("quality_score", 0)
    retry_count   = state.get("retry_count", 0)
    final_report  = state.get("final_report", "")
    audit_result  = state.get("audit_result", "")

    # Decision tree
    if audit_result:
        next_agent = "FINISH"

    elif final_report:
        next_agent = "audit"

    elif analysis and (quality_score >= 7 or retry_count >= 2):
        next_agent = "report"

    elif analysis and quality_score > 0 and quality_score < 7:
        next_agent = "improve"

    elif analysis and quality_score == 0:
        next_agent = "evaluation"

    elif memory_stored and not analysis:
        next_agent = "analysis"

    elif sources and not memory_stored:
        next_agent = "memory"

    else:
        next_agent = "research"

    print(f"  Decision → {next_agent.upper()}")

    return {
        "current_agent": "supervisor",
        "next_agent": next_agent,
        "execution_logs": log("Supervisor", f"Routing to: {next_agent.upper()}"),
    }


# =============================================================
# AGENT 1 — RESEARCH AGENT
# =============================================================

def research_agent(state: MultiAgentState) -> dict:
    """
    Plans a research strategy and collects web sources via Tavily.

    Identity: Research Specialist
    Tools used: LLM (planning + query extraction), TavilySearch
    Output: research_plan, search_queries, sources (accumulated)

    On retry cycles, it uses the existing search_queries that were
    set by the Improve Agent — it does NOT regenerate them.
    """
    print("\n" + "-" * 55)
    print("[RESEARCH AGENT] Planning and collecting research...")

    llm       = get_llm()
    tool_name = state["tool_name"]

    # If Improve Agent already set new queries, use those directly
    existing_queries = state.get("search_queries") or []
    existing_sources = state.get("sources") or []

    if existing_queries and existing_sources:
        # This is a retry — Improve Agent already set new targeted queries
        queries   = existing_queries
        plan_text = state.get("research_plan", "")
        print(f"  Using {len(queries)} improved queries from Improve Agent.")
    else:
        # First run — generate plan then extract queries
        plan_response = llm.invoke([
            SystemMessage(content=RESEARCH_AGENT_SYSTEM),
            HumanMessage(content=PLANNER_PROMPT.format(tool_name=tool_name)),
        ])
        plan_text = plan_response.content

        query_response = llm.invoke([
            SystemMessage(content=RESEARCH_AGENT_SYSTEM),
            HumanMessage(content=QUERY_EXTRACTION_PROMPT.format(
                tool_name=tool_name,
                plan=plan_text,
            )),
        ])

        default_queries = [
            f"{tool_name} overview and introduction",
            f"{tool_name} main features and capabilities",
            f"{tool_name} architecture and how it works",
            f"{tool_name} real-world use cases and examples",
            f"{tool_name} advantages limitations and alternatives",
        ]
        queries = _parse_json_list(query_response.content.strip(), default_queries)

    # Search the web for each query
    new_sources: list[dict] = []
    for query in queries:
        print(f"  Searching: {query}")
        results = tavily_search(query)
        new_sources.extend(results)

    all_sources = existing_sources + new_sources
    print(f"  +{len(new_sources)} new sources (total={len(all_sources)})")

    return {
        "current_agent":  "research",
        "research_plan":  plan_text if not existing_sources else state.get("research_plan", ""),
        "search_queries": queries,
        "sources":        all_sources,
        "memory_stored":  False,   # New sources must be re-stored
        "execution_logs": log("Research Agent",
            f"Collected {len(new_sources)} sources (total={len(all_sources)})."
        ),
    }


# =============================================================
# AGENT 2 — MEMORY AGENT
# =============================================================

def memory_agent(state: MultiAgentState) -> dict:
    """
    Persists all collected source documents into ChromaDB.

    Identity: Knowledge Persistence Specialist
    Tools used: ChromaDB (write)
    Output: memory_stored = True
    """
    print("\n" + "-" * 55)
    print("[MEMORY AGENT] Storing documents in ChromaDB...")

    vector_store = get_vector_store()
    sources: list[dict] = state.get("sources") or []

    texts, metadatas, ids = [], [], []
    for source in sources:
        content = source.get("content", "").strip()
        if not content:
            continue
        texts.append(content)
        metadatas.append({
            "url":   source.get("url", ""),
            "query": source.get("query", ""),
            "tool":  state["tool_name"],
        })
        ids.append(str(uuid.uuid4()))

    if texts:
        vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    print(f"  Stored {len(texts)} documents.")

    return {
        "current_agent":  "memory",
        "memory_stored":  True,
        "execution_logs": log("Memory Agent", f"Stored {len(texts)} documents in ChromaDB."),
    }


# =============================================================
# AGENT 3 — ANALYSIS AGENT
# =============================================================

def analysis_agent(state: MultiAgentState) -> dict:
    """
    Synthesizes all collected sources into a structured analysis.

    Identity: Research Synthesis Specialist
    Tools used: LLM (with analysis system prompt)
    Output: analysis
    """
    print("\n" + "-" * 55)
    print("[ANALYSIS AGENT] Synthesizing research...")

    llm     = get_llm()
    sources = state.get("sources") or []

    research_text = "\n\n---\n\n".join(
        f"Source: {s.get('url', 'N/A')}\n{s.get('content', '').strip()}"
        for s in sources
        if s.get("content", "").strip()
    ) or "No research data was collected."

    response = llm.invoke([
        SystemMessage(content=ANALYSIS_AGENT_SYSTEM),
        HumanMessage(content=ANALYSIS_PROMPT.format(
            tool_name=state["tool_name"],
            research=research_text[:MAX_RESEARCH_CHARS],
        )),
    ])
    analysis = response.content

    return {
        "current_agent":  "analysis",
        "analysis":       analysis,
        "quality_score":  0,    # Reset so Evaluation Agent scores fresh
        "execution_logs": log("Analysis Agent",
            f"Analysis complete ({len(analysis)} characters)."
        ),
    }


# =============================================================
# AGENT 4 — EVALUATION AGENT
# =============================================================

def evaluation_agent(state: MultiAgentState) -> dict:
    """
    Scores research quality 1-10 using Pydantic structured output.

    Identity: Quality Control Specialist
    Tools used: LLM with structured output (QualityEvaluation)
    Output: quality_score, missing_information, quality_feedback, retry_count
    """
    print("\n" + "-" * 55)
    print("[EVALUATION AGENT] Scoring research quality...")

    llm       = get_llm()
    evaluator = llm.with_structured_output(QualityEvaluation)

    result: QualityEvaluation = evaluator.invoke([
        SystemMessage(content=EVALUATION_AGENT_SYSTEM),
        HumanMessage(content=EVALUATION_PROMPT.format(analysis=state["analysis"])),
    ])

    score         = result.score
    missing_info  = result.missing_information
    current_retry = state.get("retry_count", 0)

    print(f"  Score            : {score}/10")
    print(f"  Strengths        : {result.strengths}")
    print(f"  Weaknesses       : {result.weaknesses}")
    print(f"  Missing          : {missing_info}")
    print(f"  Reason           : {result.reason}")

    # Pre-increment retry_count when quality is insufficient
    new_retry = current_retry + 1 if score < 7 else current_retry

    feedback = (
        f"Score: {score}/10 | "
        f"Strengths: {result.strengths} | "
        f"Weaknesses: {result.weaknesses} | "
        f"Missing: {missing_info}"
    )

    return {
        "current_agent":       "evaluation",
        "quality_score":       score,
        "missing_information": missing_info,
        "quality_feedback":    feedback,
        "retry_count":         new_retry,
        "execution_logs": log("Evaluation Agent",
            f"Score={score}/10 | Retries={new_retry} | {result.reason}"
        ),
    }


# =============================================================
# AGENT 5 — IMPROVE AGENT
# =============================================================

def improve_agent(state: MultiAgentState) -> dict:
    """
    Generates targeted search queries to fill research gaps.

    Identity: Gap Analysis Specialist
    Tools used: LLM + keyword-to-query mapping
    Output: search_queries (improved), memory_stored = False

    Strategy:
    1. Keyword matching on missing_information → instant targeted queries
    2. LLM fills remaining slots with context-aware queries
    """
    print("\n" + "-" * 55)
    retry_count = state.get("retry_count", 0)
    print(f"[IMPROVE AGENT] Generating targeted queries (retry #{retry_count})...")

    llm          = get_llm()
    tool_name    = state["tool_name"]
    missing_info = state.get("missing_information", "")
    quality_score = state.get("quality_score", 0)

    # Step 1 — Keyword-based targeted queries
    keyword_queries = build_keyword_queries(tool_name, missing_info)
    print(f"  Keyword-matched: {len(keyword_queries)} queries")

    # Step 2 — LLM fills remaining slots
    if len(keyword_queries) < 5:
        slots_needed = 5 - len(keyword_queries)
        response = llm.invoke([
            SystemMessage(content=IMPROVE_AGENT_SYSTEM),
            HumanMessage(content=IMPROVE_PROMPT.format(
                tool_name=tool_name,
                missing_information=missing_info,
                analysis_preview=state.get("analysis", "")[:2000],
                slots=slots_needed,
            )),
        ])
        fallback = [
            f"{tool_name} technical deep-dive",
            f"{tool_name} production deployment",
            f"{tool_name} performance benchmarks",
            f"{tool_name} developer community feedback",
            f"{tool_name} comparison with alternatives 2024",
        ]
        extra = _parse_json_list(response.content.strip(), fallback)
        keyword_queries.extend(extra[:slots_needed])

    queries = keyword_queries[:5]
    print(f"  Final queries ({len(queries)}):")
    for q in queries:
        print(f"    - {q}")

    return {
        "current_agent":  "improve",
        "search_queries": queries,
        "memory_stored":  False,   # Force Memory Agent to re-store
        "execution_logs": log("Improve Agent",
            f"Generated {len(queries)} targeted queries (retry #{retry_count})."
        ),
    }


# =============================================================
# AGENT 6 — REPORT AGENT
# =============================================================

def report_agent(state: MultiAgentState) -> dict:
    """
    Generates the final professional research report.

    Identity: Professional Report Writer
    Tools used: LLM (with report system prompt), file I/O
    Output: final_report (also saved to output/<tool>.md)

    Appends ## 8. References from collected source URLs.
    """
    print("\n" + "-" * 55)
    print("[REPORT AGENT] Generating final report...")

    llm       = get_llm()
    tool_name = state["tool_name"]
    sources   = state.get("sources") or []

    response = llm.invoke([
        SystemMessage(content=REPORT_AGENT_SYSTEM),
        HumanMessage(content=REPORT_PROMPT.format(
            tool_name=tool_name,
            score=state.get("quality_score", 0),
            analysis=state["analysis"],
        )),
    ])
    report = response.content

    # Append references section
    report = report + build_references(sources)

    # Save to disk
    report_path = save_report(tool_name, report)
    print(f"  Report saved → {report_path}")

    return {
        "current_agent":  "report",
        "final_report":   report,
        "execution_logs": log("Report Agent",
            f"Report generated ({len(report)} chars) → {report_path}"
        ),
    }


# =============================================================
# AGENT 7 — AUDIT AGENT
# =============================================================

def audit_agent(state: MultiAgentState) -> dict:
    """
    Records a structured audit trail for the research session.

    Identity: Session Documentation Specialist
    Tools used: file I/O
    Output: audit_result (also saved to audit/<tool>_audit.txt)

    Records: tool name, timestamp, sources, quality score, retries.
    """
    print("\n" + "-" * 55)
    print("[AUDIT AGENT] Recording session audit trail...")

    sources   = state.get("sources") or []
    score     = state.get("quality_score", 0)
    retries   = state.get("retry_count", 0)
    tool_name = state["tool_name"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    audit = (
        f"{'=' * 44}\n"
        f"  MULTI-AGENT RESEARCH AUDIT\n"
        f"{'=' * 44}\n"
        f"  Tool Name     : {tool_name}\n"
        f"  Timestamp     : {timestamp}\n"
        f"  Sources Found : {len(sources)}\n"
        f"  Quality Score : {score}/10\n"
        f"  Retry Count   : {retries}\n"
        f"  Agents Used   : Supervisor, Research, Memory, Analysis,\n"
        f"                   Evaluation, Report, Audit\n"
        f"{'=' * 44}\n"
    )

    audit_path = save_audit(tool_name, audit)
    print(f"  Audit saved → {audit_path}")
    print(audit)

    return {
        "current_agent":  "audit",
        "audit_result":   audit,
        "execution_logs": log("Audit Agent", f"Audit saved → {audit_path}"),
    }


# nodes.py
# All LangGraph node functions for the AI Tool Research Agent.


import json
import os
import re
import uuid
from datetime import datetime

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.embeddings.fake import DeterministicFakeEmbedding
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from prompts import ANALYSIS_PROMPT, EVALUATION_PROMPT, PLANNER_PROMPT, REPORT_PROMPT
from state import AgentState, QualityScore

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

CHROMA_DIR    = "./chroma_db"
OUTPUT_DIR    = "./output"          # Saved markdown reports
AUDIT_DIR     = "./audit"           # Saved audit text files
MAX_RESEARCH_CHARS = 12_000         # Guard against token-limit overflow
LABEL_WIDTH   = 20                  # Column width for progress display


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def get_llm() -> ChatOpenAI:
    """Returns a ChatOpenAI instance routed through OpenRouter → Gemini 2.5 Flash."""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "google/gemini-2.5-flash"),
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.3,
        max_tokens=1500,
    )


def get_vector_store() -> Chroma:
    """Returns a persistent ChromaDB store backed by DeterministicFakeEmbedding."""
    embedding = DeterministicFakeEmbedding(size=512)
    return Chroma(
        collection_name="ai_tool_research",
        embedding_function=embedding,
        persist_directory=CHROMA_DIR,
    )


def log(message: str) -> list[str]:
    """Prints a timestamped log line and returns it as a list for state merging."""
    entry = f"[{datetime.now():%H:%M:%S}] {message}"
    print(entry)
    return [entry]


def _tick(label: str) -> None:
    """
    Prints a single-line progress checkmark at the end of each node.

    Example output:
        Planner              ✓
        Collect              ✓
    """
    print(f"  {label:<{LABEL_WIDTH}} ✓")


def _parse_json_list(raw: str, fallback: list[str]) -> list[str]:
    """Extracts the first JSON array from a string; returns fallback on failure."""
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    try:
        result = json.loads(match.group()) if match else []
        if isinstance(result, list) and len(result) > 0:
            return result
    except Exception:
        pass
    return fallback


def _safe_filename(tool_name: str) -> str:
    """Converts a tool name to a filesystem-safe string."""
    return re.sub(r"[^\w\-]", "_", tool_name).strip("_")


def _build_references(sources: list[dict]) -> str:
    """
    Builds the ## 8. References section from collected sources.

    - Deduplicates URLs while preserving order.
    - Returns a formatted numbered markdown list.
    """
    seen: set[str] = set()
    unique_urls: list[str] = []

    for s in sources:
        url = s.get("url", "").strip()
        if url and url not in seen:
            seen.add(url)
            unique_urls.append(url)

    if not unique_urls:
        return "\n\n## 8. References\n\nNo sources were collected.\n"

    lines = ["\n\n## 8. References\n"]
    for i, url in enumerate(unique_urls, start=1):
        lines.append(f"{i}. {url}")

    return "\n".join(lines) + "\n"


def _build_keyword_queries(tool_name: str, missing_info: str) -> list[str]:
    """
    Maps missing_information keywords to targeted, specific search queries.

    This is the core of the smarter retry logic (Feature 6):
    instead of repeating previous queries, it inspects what the evaluator
    flagged as absent and produces queries that directly fill those gaps.

    Examples:
        "documentation" missing  →  "<tool> official documentation"
        "limitations" missing    →  "<tool> limitations and drawbacks"
        "comparison" missing     →  "<tool> vs LangGraph comparison"
    """
    text = missing_info.lower()
    queries: list[str] = []

    # Ordered: each tuple is (list of trigger keywords, search query to generate)
    topic_map = [
        (
            ["documentation", "docs", "official site"],
            f"{tool_name} official documentation",
        ),
        (
            ["limitation", "drawback", "weakness", "cons", "disadvantage"],
            f"{tool_name} limitations and drawbacks",
        ),
        (
            ["comparison", "alternative", " vs ", "versus"],
            f"{tool_name} vs LangGraph vs CrewAI comparison alternatives",
        ),
        (
            ["use case", "example", "real-world", "application"],
            f"{tool_name} real-world use cases and examples",
        ),
        (
            ["architecture", "internals", "how it works", "mechanism"],
            f"{tool_name} architecture technical internals",
        ),
        (
            ["feature", "capability", "function", "what can"],
            f"{tool_name} complete features and capabilities",
        ),
        (
            ["performance", "scalability", "speed", "benchmark"],
            f"{tool_name} performance benchmarks scalability",
        ),
        (
            ["tutorial", "guide", "getting started", "quickstart"],
            f"{tool_name} getting started tutorial guide",
        ),
        (
            ["community", "support", "ecosystem", "plugin"],
            f"{tool_name} community ecosystem and support",
        ),
        (
            ["pricing", "cost", "license", "free", "paid"],
            f"{tool_name} pricing licensing free vs paid",
        ),
    ]

    for keywords, query in topic_map:
        if any(kw in text for kw in keywords) and len(queries) < 5:
            queries.append(query)

    return queries


def _save_report(tool_name: str, report: str) -> str:
    """
    Saves the final report to output/<tool_name>.md.
    Creates the output directory if it does not exist.
    Returns the saved file path.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"{_safe_filename(tool_name)}.md"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


def _save_audit(tool_name: str, audit_text: str) -> str:
    """
    Saves the audit record to audit/<tool_name>_audit.txt.
    Creates the audit directory if it does not exist.
    Returns the saved file path.
    """
    os.makedirs(AUDIT_DIR, exist_ok=True)
    filename = f"{_safe_filename(tool_name)}_audit.txt"
    path = os.path.join(AUDIT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(audit_text)
    return path


# ─────────────────────────────────────────────────────────────
# Node 1 — Planner
# ─────────────────────────────────────────────────────────────

def planner_node(state: AgentState) -> dict:
    """
    Generates a structured research plan and 5 targeted search queries
    for the given AI tool.

    Steps:
        1. Calls the LLM with PLANNER_PROMPT to produce a research plan.
        2. Makes a second call to extract exactly 5 queries as a JSON array.
        3. Falls back to sensible default queries if JSON parsing fails.
    """
    print("\n" + "─" * 55)
    print("[Planner] Generating research plan...")

    llm = get_llm()
    tool_name = state["tool_name"]

    # Step 1 – comprehensive research plan
    plan_response = llm.invoke(
        [HumanMessage(content=PLANNER_PROMPT.format(tool_name=tool_name))]
    )
    plan_text = plan_response.content

    # Step 2 – derive 5 concrete search queries from the plan
    query_prompt = (
        f"Based on the research plan below for '{tool_name}', "
        "generate exactly 5 specific and diverse web search queries.\n"
        "Return ONLY a valid JSON array of 5 strings. No extra text.\n\n"
        f"Plan:\n{plan_text}"
    )
    query_response = llm.invoke([HumanMessage(content=query_prompt)])

    default_queries = [
        f"{tool_name} overview and introduction",
        f"{tool_name} main features and capabilities",
        f"{tool_name} architecture and how it works",
        f"{tool_name} real-world use cases and examples",
        f"{tool_name} advantages limitations and alternatives",
    ]
    queries = _parse_json_list(query_response.content.strip(), default_queries)

    _tick("Planner")
    return {
        "research_plan": plan_text,
        "search_queries": queries,
        "execution_logs": log(
            f"[Planner] Plan ready. Generated {len(queries)} search queries."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 2 — Collect
# ─────────────────────────────────────────────────────────────

def collect_node(state: AgentState) -> dict:
    """
    Searches the web using Tavily for every query in state['search_queries'].

    - Uses advanced search depth for richer content.
    - Accumulates new results on top of existing sources so prior research
      is preserved across retry cycles.
    """
    print("\n" + "─" * 55)
    print("[Collect] Searching the web via Tavily...")

    search_tool = TavilySearch(max_results=3, search_depth="advanced")
    queries = state["search_queries"]
    existing_sources: list[dict] = state.get("sources") or []
    new_sources: list[dict] = []

    for query in queries:
        print(f"  Query: {query}")
        try:
            response = search_tool.invoke({"query": query})
            results = (
                response.get("results", []) if isinstance(response, dict) else []
            )
            for r in results:
                new_sources.append(
                    {
                        "url": r.get("url", ""),
                        "content": r.get("content", ""),
                        "query": query,
                    }
                )
        except Exception as exc:
            print(f"  [!] Tavily error for '{query}': {exc}")

    all_sources = existing_sources + new_sources

    _tick("Collect")
    return {
        "sources": all_sources,
        "execution_logs": log(
            f"[Collect] +{len(new_sources)} new documents "
            f"(total={len(all_sources)})."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 3 — Store Memory
# ─────────────────────────────────────────────────────────────

def store_memory_node(state: AgentState) -> dict:
    """
    Persists all collected source documents into ChromaDB.

    - Each document is stored with its URL, originating query, and
      the tool name as metadata for future retrieval.
    - Documents with empty content are silently skipped.
    """
    print("\n" + "─" * 55)
    print("[StoreMemory] Persisting documents in ChromaDB...")

    vector_store = get_vector_store()
    sources: list[dict] = state.get("sources") or []

    texts, metadatas, ids = [], [], []

    for source in sources:
        content = source.get("content", "").strip()
        if not content:
            continue
        texts.append(content)
        metadatas.append(
            {
                "url": source.get("url", ""),
                "query": source.get("query", ""),
                "tool": state["tool_name"],
            }
        )
        ids.append(str(uuid.uuid4()))

    if texts:
        vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    _tick("Store Memory")
    return {
        "execution_logs": log(
            f"[StoreMemory] Stored {len(texts)} documents in ChromaDB."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 4 — Analyze
# ─────────────────────────────────────────────────────────────

def analyze_node(state: AgentState) -> dict:
    """
    Synthesizes all collected sources into a structured analysis using the LLM.

    - Uses ANALYSIS_PROMPT from prompts.py.
    - Concatenates all source content, capped at MAX_RESEARCH_CHARS to
      stay within model token limits.
    """
    print("\n" + "─" * 55)
    print("[Analyze] Synthesizing collected research...")

    llm = get_llm()
    sources: list[dict] = state.get("sources") or []

    # Build one combined research block from all source texts
    research_text = "\n\n---\n\n".join(
        f"Source: {s.get('url', 'N/A')}\n{s.get('content', '').strip()}"
        for s in sources
        if s.get("content", "").strip()
    ) or "No research data was collected."

    prompt = ANALYSIS_PROMPT.format(
        tool_name=state["tool_name"],
        research=research_text[:MAX_RESEARCH_CHARS],
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    analysis = response.content

    _tick("Analyze")
    return {
        "analysis": analysis,
        "execution_logs": log(
            f"[Analyze] Analysis complete ({len(analysis)} characters)."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 5 — Evaluate
# ─────────────────────────────────────────────────────────────

def evaluate_node(state: AgentState) -> dict:
    """
    Scores the research quality from 1–10 using structured Pydantic output.

    Now returns a richer breakdown (Feature 5):
        score, strengths, weaknesses, missing_information, reason

    - missing_information is stored in state so that improve_node can
      generate smarter, gap-filling queries on the next retry cycle.
    - retry_count is pre-incremented when score < 7 so the router
      can immediately compare against the max-retry ceiling.
    """
    print("\n" + "─" * 55)
    print("[Evaluate] Scoring research quality with structured output...")

    llm = get_llm()
    evaluator = llm.with_structured_output(QualityScore)

    prompt = EVALUATION_PROMPT.format(analysis=state["analysis"])
    result: QualityScore = evaluator.invoke([HumanMessage(content=prompt)])

    score          = result.score
    strengths      = result.strengths
    weaknesses     = result.weaknesses
    missing_info   = result.missing_information
    reason         = result.reason
    current_retry  = state.get("retry_count", 0)

    # Print full evaluation breakdown
    print(f"  Score            : {score}/10")
    print(f"  Strengths        : {strengths}")
    print(f"  Weaknesses       : {weaknesses}")
    print(f"  Missing Info     : {missing_info}")
    print(f"  Reason           : {reason}")

    # Pre-increment retry so the router sees the upcoming retry number
    new_retry = current_retry + 1 if score < 7 else current_retry

    _tick("Evaluate")
    return {
        "quality_score":      score,
        "missing_information": missing_info,
        "retry_count":        new_retry,
        "execution_logs": log(
            f"[Evaluate] Score={score}/10 | Retries={new_retry} | {reason}"
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 6 — Improve Queries  (smarter retry — Feature 6)
# ─────────────────────────────────────────────────────────────

def improve_node(state: AgentState) -> dict:
    """
    Generates improved, gap-filling search queries when research quality
    is insufficient (score < 7).

    Smarter retry strategy (Feature 6):
        1. Read missing_information set by evaluate_node.
        2. Use _build_keyword_queries() to map missing topics to specific
           query patterns (documentation, limitations, comparison, etc.).
        3. If keyword matching produces fewer than 5 queries, ask the LLM
           to fill the remaining slots using missing_information as context.
        4. Never repeats previous queries — always addresses identified gaps.
    """
    print("\n" + "─" * 55)
    retry_count = state.get("retry_count", 0)
    print(f"[Improve] Generating targeted queries for retry #{retry_count}...")

    llm          = get_llm()
    tool_name    = state["tool_name"]
    missing_info = state.get("missing_information", "")
    quality_score = state.get("quality_score", 0)

    # Step 1 – keyword-based targeted queries from evaluation gaps
    keyword_queries = _build_keyword_queries(tool_name, missing_info)
    print(f"  Keyword-matched queries: {len(keyword_queries)}")

    # Step 2 – ask LLM to fill remaining slots if keyword matching fell short
    if len(keyword_queries) < 5:
        slots_needed = 5 - len(keyword_queries)
        llm_prompt = (
            f"The research about '{tool_name}' scored {quality_score}/10.\n\n"
            f"The evaluator identified these missing topics:\n{missing_info}\n\n"
            f"The following queries are already planned:\n"
            + "\n".join(f"- {q}" for q in keyword_queries)
            + f"\n\nGenerate exactly {slots_needed} ADDITIONAL search queries "
            "that cover different missing topics not addressed above.\n"
            "Return ONLY a valid JSON array of strings. No extra text."
        )
        llm_response = llm.invoke([HumanMessage(content=llm_prompt)])

        fallback = [
            f"{tool_name} technical deep-dive documentation",
            f"{tool_name} production deployment best practices",
            f"{tool_name} performance benchmarks and scalability",
            f"{tool_name} community reviews and developer feedback",
            f"{tool_name} comparison with similar tools",
        ]
        llm_queries = _parse_json_list(llm_response.content.strip(), fallback)
        keyword_queries.extend(llm_queries[:slots_needed])

    queries = keyword_queries[:5]
    print(f"  Final improved queries ({len(queries)}):")
    for q in queries:
        print(f"    - {q}")

    _tick("Improve Queries")
    return {
        "search_queries": queries,
        "execution_logs": log(
            f"[Improve] Generated {len(queries)} targeted queries "
            f"(retry #{retry_count})."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 7 — Report
# ─────────────────────────────────────────────────────────────

def report_node(state: AgentState) -> dict:
    """
    Generates the final professional research report using the LLM.

    Improvements (Features 3 & 7):
        - REPORT_PROMPT now instructs the LLM to include a Table of Contents.
        - After the LLM response, a ## 8. References section is appended
          automatically using deduplicated URLs from state['sources'].
        - The complete report (with references) is saved to
          output/<tool_name>.md  (Feature 1).
    """
    print("\n" + "─" * 55)
    print("[Report] Generating final professional report...")

    llm = get_llm()
    tool_name = state["tool_name"]
    sources: list[dict] = state.get("sources") or []

    # Generate the main report body via LLM
    prompt = REPORT_PROMPT.format(
        tool_name=tool_name,
        analysis=state["analysis"],
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    report = response.content

    # Append the References section (Feature 3)
    references = _build_references(sources)
    report = report + references

    # Save report to output/<tool_name>.md (Feature 1)
    report_path = _save_report(tool_name, report)
    print(f"  Report saved → {report_path}")

    _tick("Generate Report")
    return {
        "final_report": report,
        "execution_logs": log(
            f"[Report] Report generated ({len(report)} chars) → {report_path}"
        ),
    }


# ─────────────────────────────────────────────────────────────
# Node 8 — Audit
# ─────────────────────────────────────────────────────────────

def audit_node(state: AgentState) -> dict:
    """
    Records a structured audit trail for the completed research session.

    Captures (Feature 2):
        - Tool name
        - Timestamp
        - Number of sources collected
        - Final quality score
        - Total retry count

    Saves the audit record to audit/<tool_name>_audit.txt.
    """
    print("\n" + "─" * 55)
    print("[Audit] Recording session audit trail...")

    sources: list[dict] = state.get("sources") or []
    score     = state.get("quality_score", 0)
    retries   = state.get("retry_count", 0)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tool_name = state["tool_name"]

    audit = (
        f"{'=' * 44}\n"
        f"  RESEARCH AUDIT RECORD\n"
        f"{'=' * 44}\n"
        f"  Tool Name     : {tool_name}\n"
        f"  Timestamp     : {timestamp}\n"
        f"  Sources Found : {len(sources)}\n"
        f"  Quality Score : {score}/10\n"
        f"  Retry Count   : {retries}\n"
        f"{'=' * 44}\n"
    )

    # Save to audit/<tool_name>_audit.txt (Feature 2)
    audit_path = _save_audit(tool_name, audit)
    print(f"  Audit saved   → {audit_path}")
    print(audit)

    _tick("Audit")
    return {
        "audit_result": audit,
        "execution_logs": log(
            f"[Audit] Audit record saved → {audit_path}"
        ),
    }

# =============================================================
# tools.py — Shared tools used by all agents
# =============================================================
# Centralizing tools here means every agent uses the same
# configured instances — consistent settings, one place to change.
# =============================================================

import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.embeddings.fake import DeterministicFakeEmbedding
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Paths  (absolute so they work from any working directory)
# ─────────────────────────────────────────────────────────────

LAB3_DIR   = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(LAB3_DIR, "chroma_db")
OUTPUT_DIR = os.path.join(LAB3_DIR, "output")
AUDIT_DIR  = os.path.join(LAB3_DIR, "audit")

MAX_RESEARCH_CHARS = 12_000


# ─────────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────────

def get_llm() -> ChatOpenAI:
    """Returns a ChatOpenAI instance routed through OpenRouter → Gemini 2.5 Flash."""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "google/gemini-2.5-flash"),
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.3,
        max_tokens=1500,
    )


# ─────────────────────────────────────────────────────────────
# Vector Store
# ─────────────────────────────────────────────────────────────

def get_vector_store() -> Chroma:
    """Returns a persistent ChromaDB store with DeterministicFakeEmbedding."""
    embedding = DeterministicFakeEmbedding(size=512)
    return Chroma(
        collection_name="multi_agent_research",
        embedding_function=embedding,
        persist_directory=CHROMA_DIR,
    )


# ─────────────────────────────────────────────────────────────
# Web Search
# ─────────────────────────────────────────────────────────────

def tavily_search(query: str, max_results: int = 3) -> list[dict]:
    """
    Searches the web using Tavily and returns a list of
    {"url": ..., "content": ..., "query": ...} dicts.
    """
    search_tool = TavilySearch(max_results=max_results, search_depth="advanced")
    try:
        response = search_tool.invoke({"query": query})
        results = response.get("results", []) if isinstance(response, dict) else []
        return [
            {
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "query": query,
            }
            for r in results
        ]
    except Exception as exc:
        print(f"  [!] Tavily error for '{query}': {exc}")
        return []


# ─────────────────────────────────────────────────────────────
# File I/O helpers
# ─────────────────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    """Converts a tool name to a filesystem-safe string."""
    return re.sub(r"[^\w\-]", "_", name).strip("_")


def save_report(tool_name: str, report: str) -> str:
    """Saves the report to output/<tool_name>.md. Returns path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{safe_filename(tool_name)}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


def save_audit(tool_name: str, audit_text: str) -> str:
    """Saves the audit record to audit/<tool_name>_audit.txt. Returns path."""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    path = os.path.join(AUDIT_DIR, f"{safe_filename(tool_name)}_audit.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(audit_text)
    return path


def build_references(sources: list[dict]) -> str:
    """Builds a ## 8. References section from deduplicated source URLs."""
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
    for i, url in enumerate(unique_urls, 1):
        lines.append(f"{i}. {url}")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────

def log(agent_name: str, message: str) -> list[str]:
    """
    Prints a timestamped log entry tagged with the agent name.
    Returns it as a list for LangGraph's operator.add reducer.
    """
    entry = f"[{datetime.now():%H:%M:%S}] [{agent_name.upper()}] {message}"
    print(entry)
    return [entry]


# ─────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────

def build_keyword_queries(tool_name: str, missing_info: str) -> list[str]:
    """
    Maps missing_information keywords to targeted search queries.
    Used by the Improve Agent for smarter retry logic.
    """
    text = missing_info.lower()
    queries: list[str] = []

    topic_map = [
        (["documentation", "docs", "official"], f"{tool_name} official documentation"),
        (["limitation", "drawback", "weakness", "cons"], f"{tool_name} limitations and drawbacks"),
        (["comparison", "alternative", " vs "], f"{tool_name} vs alternatives comparison"),
        (["use case", "example", "real-world"], f"{tool_name} real-world use cases examples"),
        (["architecture", "internals", "how it works"], f"{tool_name} architecture technical internals"),
        (["feature", "capability"], f"{tool_name} complete features and capabilities"),
        (["performance", "scalability", "benchmark"], f"{tool_name} performance benchmarks"),
        (["tutorial", "guide", "getting started"], f"{tool_name} getting started tutorial 2024"),
        (["community", "support", "ecosystem"], f"{tool_name} community ecosystem support"),
        (["pricing", "cost", "license"], f"{tool_name} pricing and licensing"),
    ]

    for keywords, query in topic_map:
        if any(kw in text for kw in keywords) and len(queries) < 5:
            queries.append(query)

    return queries

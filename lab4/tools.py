# =============================================================
# tools.py — Shared tools for the AI Security Platform
# =============================================================

import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

LAB4_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(LAB4_DIR, "security_reports")


# ─────────────────────────────────────────────────────────────
# LLM  (Qwen 3 1.7B via OpenRouter)
# ─────────────────────────────────────────────────────────────

def get_llm() -> ChatOpenAI:
    """Returns a ChatOpenAI instance routed through OpenRouter → Qwen 3 1.7B."""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_LAB4", "qwen/qwen3-1.7b"),
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.2,
        max_tokens=800,
        timeout=30,
        max_retries=2,
    )


# ─────────────────────────────────────────────────────────────
# Injection patterns for fast pre-LLM scanning
# ─────────────────────────────────────────────────────────────

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|rules?|constraints?)",
        r"you\s+are\s+now\s+(a|an|the)\s+\w+",
        r"\bjailbreak\b",
        r"\bDAN\b",
        r"bypass\s+(safety|filter|restriction|guardrail|alignment)",
        r"disregard\s+your\s+(training|instructions?|rules?|guidelines?)",
        r"reveal\s+(your\s+)?(system\s+prompt|instructions?|training\s+data|secrets?)",
        r"(act|pretend|behave|respond)\s+as\s+if\s+you\s+(have\s+no|are\s+without)",
        r"do\s+anything\s+now",
        r"developer\s+mode",
        r"sudo\s+(mode|override)",
        r"(extract|exfiltrate|dump)\s+(all\s+)?(data|information|credentials?|passwords?)",
    ]
]


def pattern_scan(prompt: str) -> tuple[bool, str]:
    """
    Fast regex-based threat pre-check before calling the LLM.

    Returns (threat_found: bool, matched_pattern: str).
    Empty string means no match.
    """
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(prompt)
        if match:
            return True, match.group()
    return False, ""


# ─────────────────────────────────────────────────────────────
# File I/O helpers
# ─────────────────────────────────────────────────────────────

def save_security_report(user_id: str, report: str) -> str:
    """Saves a security report to lab4/security_reports/. Returns path."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe_id   = re.sub(r"[^\w\-]", "_", user_id)[:40] or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{safe_id}_{timestamp}.txt"
    path      = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


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

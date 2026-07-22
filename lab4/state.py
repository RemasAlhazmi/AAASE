# =============================================================
# state.py — Shared state for the AI Security Platform
# =============================================================

import operator
from typing import Annotated, Dict, List
from typing import TypedDict

from pydantic import BaseModel, Field


class SecurityState(TypedDict):
    """
    The shared state that flows through every security agent.

    Tracks the full lifecycle of a prompt from intake through
    threat detection, hardening, execution, monitoring, and audit.
    """

    # ── User input ───────────────────────────────────────────
    user_id: str
    user_prompt: str

    # ── Supervisor control ───────────────────────────────────
    current_agent: str       # agent that just finished
    next_agent: str          # agent the supervisor chose next

    # ── Security Gate ────────────────────────────────────────
    threat_detected: bool
    threat_type: str         # "prompt_injection" | "jailbreak" | "data_extraction" | "none"
    threat_score: float      # 0.0 – 1.0

    # ── LLM Hardener ─────────────────────────────────────────
    hardened_prompt: str
    defense_strategy: str

    # ── Safe Executor ────────────────────────────────────────
    safe_response: str

    # ── Behavior Monitor ─────────────────────────────────────
    anomaly_score: float
    requests_per_minute: int
    failed_requests: int
    is_anomalous: bool

    # ── Security Logger ──────────────────────────────────────
    security_events: List[Dict]
    alert_level: str         # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"

    # ── Security Auditor ─────────────────────────────────────
    security_report: str

    # ── Shared (append-only) ─────────────────────────────────
    execution_logs: Annotated[List[str], operator.add]


# =============================================================
# Pydantic schema for structured threat detection output
# =============================================================

class ThreatResult(BaseModel):
    """
    Forces the LLM to return a structured threat assessment
    instead of free text. Used by the Security Gate agent.
    """

    threat_detected: bool = Field(
        description="True if a security threat was detected in the prompt.",
    )
    threat_type: str = Field(
        description=(
            "Category of threat: 'prompt_injection', 'jailbreak', "
            "'data_extraction', or 'none'."
        ),
    )
    threat_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 (safe) to 1.0 (certain threat).",
    )
    reason: str = Field(
        description="One-sentence explanation of why this was or was not flagged.",
    )

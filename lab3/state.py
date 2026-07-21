# =============================================================
# state.py — Shared state for the Multi-Agent Research System
# =============================================================

import operator
from typing import Annotated, Dict, List
from typing import TypedDict

from pydantic import BaseModel, Field


class MultiAgentState(TypedDict):
    """
    The shared digital clipboard that flows through every agent.

    Key difference from Lab 2:
    - Added  current_agent / next_agent  so the Supervisor can
      track who just ran and decide who runs next.
    - Added  memory_stored  flag so the Supervisor knows whether
      the Memory Agent has already persisted this batch of sources.
    - Added  quality_feedback  so the Evaluation Agent can pass
      a human-readable summary to the Report Agent.
    """

    # ── User input ───────────────────────────────────────────
    tool_name: str

    # ── Supervisor control ───────────────────────────────────
    current_agent: str      # agent that just finished
    next_agent: str         # agent the supervisor chose next

    # ── Research Agent ───────────────────────────────────────
    research_plan: str
    search_queries: List[str]

    # ── Collect (run inside Research Agent) ──────────────────
    sources: List[Dict]

    # ── Memory Agent ─────────────────────────────────────────
    memory_stored: bool     # True after Memory Agent persists sources

    # ── Analysis Agent ───────────────────────────────────────
    analysis: str

    # ── Evaluation Agent ─────────────────────────────────────
    quality_score: int
    missing_information: str
    quality_feedback: str
    retry_count: int

    # ── Report Agent ─────────────────────────────────────────
    final_report: str

    # ── Audit Agent ──────────────────────────────────────────
    audit_result: str

    # ── Shared ───────────────────────────────────────────────
    execution_logs: Annotated[List[str], operator.add]


# =============================================================
# Pydantic schema for structured LLM output
# =============================================================

class QualityEvaluation(BaseModel):
    """
    Forces the LLM to return a structured quality breakdown
    instead of free text. Used by the Evaluation Agent.
    """

    score: int = Field(
        ge=1, le=10,
        description="Overall research quality score from 1 to 10.",
    )
    strengths: str = Field(
        description="What the research covers well (1-3 sentences).",
    )
    weaknesses: str = Field(
        description="Where the research is thin or vague (1-3 sentences).",
    )
    missing_information: str = Field(
        description=(
            "Specific topics completely absent from the research, e.g. "
            "'official documentation', 'performance benchmarks', "
            "'comparison with alternatives', 'limitations'."
        ),
    )
    reason: str = Field(
        description="One-sentence overall justification for the score.",
    )

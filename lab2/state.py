from typing import TypedDict, Annotated, List, Dict
import operator

from pydantic import BaseModel, Field


class AgentState(TypedDict):
    """
    Shared state across all LangGraph nodes.
    """

    # User input
    tool_name: str

    # Planner
    research_plan: str
    search_queries: List[str]

    # Research
    sources: List[Dict]

    # Analysis
    analysis: str

    # Evaluation — score + detailed breakdown for smarter retry
    quality_score: int
    missing_information: str   # Used by improve_node to generate targeted queries
    retry_count: int

    # Final Output
    final_report: str
    audit_result: str

    # Logs
    execution_logs: Annotated[List[str], operator.add]


class QualityScore(BaseModel):
    """
    Structured output used by the evaluator (Feature 5).

    Returns a richer breakdown beyond just score + reason so that
    the improve_node can generate smarter, gap-filling queries.
    """

    score: int = Field(
        ge=1,
        le=10,
        description="Overall quality score from 1 to 10.",
    )

    strengths: str = Field(
        description="What the research covers well.",
    )

    weaknesses: str = Field(
        description="Areas where the research is weak or thin.",
    )

    missing_information: str = Field(
        description=(
            "Specific topics, sections, or data points that are completely absent "
            "from the research (e.g. 'official documentation', 'limitations', "
            "'comparison with alternatives')."
        ),
    )

    reason: str = Field(
        description="One-sentence overall justification for the score.",
    )

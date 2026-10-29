"""
MarketMind AI - Research Plan Schema and Invariant Validator
Implements Task 03 and Section 4.1.
Enforces structural decomposition, answerability, and tool mapping.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, field_validator


class EvidenceType(str, Enum):
    """Categorization of required evidence to answer a sub-question."""
    VENDOR_DOC = "vendor_doc"
    PRICING_TABLE = "pricing_table"
    PRESS_RELEASE = "press_release"
    ANALYST_NOTE = "analyst_note"
    INDEPENDENT_BENCHMARK = "independent_benchmark"
    CUSTOMER_REVIEW = "customer_review"


class QuestionPriority(str, Enum):
    """Priority level for sequencing research questions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QuestionStatus(str, Enum):
    """State machine status of a research sub-question."""
    OPEN = "open"
    ANSWERED = "answered"
    UNANSWERABLE = "unanswerable"


class CandidateTool(str, Enum):
    """Approved tools assignable to sub-questions."""
    SEARCH_INFORMATION = "search_information"
    RETRIEVE_DOCUMENT = "retrieve_document"
    CALCULATE_METRIC = "calculate_metric"
    COMPARE_COMPANIES = "compare_companies"
    SAVE_RESEARCH = "save_research"


class SubQuestion(BaseModel):
    """An atomic, answerable research question with evidence bounds."""
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(
        ...,
        description="Unique question identifier (e.g. 'Q-101')"
    )
    question_text: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description="Specific, bounded question text that a junior analyst could definitively answer"
    )
    required_evidence_type: EvidenceType = Field(
        ...,
        description="The type of empirical evidence required to answer this question"
    )
    candidate_tools: List[CandidateTool] = Field(
        ...,
        min_length=1,
        description="List of candidate tools capable of retrieving or computing this evidence"
    )
    priority: QuestionPriority = Field(
        default=QuestionPriority.HIGH,
        description="Priority ranking for scheduling research passes"
    )
    status: QuestionStatus = Field(
        default=QuestionStatus.OPEN,
        description="Current state: open, answered, or unanswerable"
    )
    resolution_notes: Optional[str] = Field(
        default=None,
        description="Summary of finding or reason marked unanswerable"
    )


class ResearchObjective(BaseModel):
    """A strategic research objective grouping 2-5 concrete sub-questions."""
    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(
        ...,
        description="Unique objective identifier (e.g. 'OBJ-1')"
    )
    title: str = Field(
        ...,
        min_length=5,
        max_length=150,
        description="Strategic title of the research objective"
    )
    description: str = Field(
        ...,
        description="Scope and business context for this objective"
    )
    sub_questions: List[SubQuestion] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="Between 2 and 5 specific sub-questions"
    )


class ResearchPlan(BaseModel):
    """The complete, validated research plan produced by the Planner."""
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(
        ...,
        description="Unique plan identifier"
    )
    target_entity_type: str = Field(
        ...,
        description="The category, market, or entity type under research"
    )
    objectives: List[ResearchObjective] = Field(
        ...,
        min_length=3,
        max_length=6,
        description="Between 3 and 6 strategic objectives"
    )
    candidate_tools: List[CandidateTool] = Field(
        default_factory=lambda: [
            CandidateTool.SEARCH_INFORMATION,
            CandidateTool.RETRIEVE_DOCUMENT,
            CandidateTool.CALCULATE_METRIC,
            CandidateTool.COMPARE_COMPANIES,
            CandidateTool.SAVE_RESEARCH
        ],
        description="Universe of tools available to this plan"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def validate_plan_invariants(plan: ResearchPlan) -> List[str]:
    """
    Code-level invariant validation for ResearchPlan (Task 04).
    Enforces rules that cannot be guaranteed by JSON schema alone:
    - 3 to 6 objectives
    - Each objective has 2 to 5 sub-questions
    - Total sub-questions bounded (6 to 25)
    - No duplicate question IDs or identical question texts
    - Every question mapped to at least 1 valid candidate tool
    - No vague / unbounded questions
    """
    errors: List[str] = []

    if len(plan.objectives) < 3 or len(plan.objectives) > 6:
        errors.append(f"Plan must have 3-6 objectives, found {len(plan.objectives)}.")

    seen_q_ids = set()
    seen_q_texts = set()
    total_questions = 0

    vague_phrases = ["analyse the market", "understand everything", "look into trends", "explore competitors"]

    for obj in plan.objectives:
        if len(obj.sub_questions) < 2 or len(obj.sub_questions) > 5:
            errors.append(
                f"Objective '{obj.objective_id}' has {len(obj.sub_questions)} sub-questions; required: 2-5."
            )

        for q in obj.sub_questions:
            total_questions += 1
            if q.question_id in seen_q_ids:
                errors.append(f"Duplicate question ID found: '{q.question_id}'.")
            seen_q_ids.add(q.question_id)

            norm_text = q.question_text.strip().lower()
            if norm_text in seen_q_texts:
                errors.append(f"Duplicate question text found: '{q.question_text}'.")
            seen_q_texts.add(norm_text)

            for vp in vague_phrases:
                if vp in norm_text:
                    errors.append(f"Unbounded/vague phrasing detected in question '{q.question_id}': '{vp}'.")

            if not q.candidate_tools:
                errors.append(f"Question '{q.question_id}' has no candidate tools assigned.")

    if total_questions > 25:
        errors.append(f"Plan exceeds maximum limit of 25 sub-questions (found {total_questions}).")

    return errors

"""
MarketMind AI - Research State Management
Task 06 requirement: fully serializable state object maintaining plan status,
evidence store, tool execution history, token/cost spend, defects, and stage.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict

from src.schemas.plan import ResearchPlan, SubQuestion, QuestionStatus
from src.schemas.evidence import EvidenceStore, EvidenceRecord
from src.schemas.report import FinalReport, ApprovalRecord


class ToolExecutionRecord(BaseModel):
    """Immutable audit record of a single tool execution."""
    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(..., description="Unique result ID generated for this execution (e.g. 'TOOL-001')")
    tool_name: str = Field(..., description="Name of the executed tool")
    arguments: Dict[str, Any] = Field(..., description="Sanitized, validated input arguments")
    result: Any = Field(..., description="Normalised structured tool result or structured error")
    is_error: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)
    latency_seconds: float = Field(default=0.0)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ResearchState(BaseModel):
    """
    Central, serializable state object passed through the MarketMind pipeline.
    Preserves all evidence, plan state, tool logs, and cost accounting.
    """
    model_config = ConfigDict(extra="forbid")

    # Run Identifiers
    run_id: str = Field(..., description="Unique identifier for the research run")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_stage: str = Field(default="intake", description="Current stage in orchestration")

    # Scope & Intake
    raw_request: str = Field(..., description="Original user prompt / client request")
    scope: Dict[str, Any] = Field(default_factory=dict, description="Normalised scope object")
    assumptions: List[str] = Field(default_factory=list, description="Explicit recorded assumptions")
    ambiguities: List[str] = Field(default_factory=list, description="Identified ambiguities")

    # Planning
    plan: Optional[ResearchPlan] = Field(default=None, description="Decomposed research plan")

    # Evidence & Tools
    evidence_store: EvidenceStore = Field(default_factory=EvidenceStore)
    tool_history: List[ToolExecutionRecord] = Field(default_factory=list)
    result_id_counter: int = Field(default=0)

    # Execution Bounds & Counters
    iteration_count: int = Field(default=0)
    tool_call_count: int = Field(default=0)
    cumulative_tokens: int = Field(default=0)
    cumulative_cost_usd: float = Field(default=0.0)
    repair_round: int = Field(default=0)
    is_incomplete: bool = Field(default=False)
    termination_reason: Optional[str] = Field(default=None)

    # Analysis & Quality Control
    comparison_matrix: Optional[Dict[str, Any]] = Field(default=None)
    draft_findings: List[Dict[str, Any]] = Field(default_factory=list)
    defect_list: List[Dict[str, Any]] = Field(default_factory=list)
    qc_verdict: Optional[str] = Field(default=None)
    qc_targeted_gap_questions: List[str] = Field(default_factory=list)

    # Deliverables & Governance
    final_report: Optional[FinalReport] = Field(default=None)
    approval: Optional[ApprovalRecord] = Field(default=None)
    status: str = Field(default="in_progress", description="in_progress, approved, rejected, terminated_early")

    def next_result_id(self) -> str:
        """Generate a sequential, monotonic result ID for tool provenance."""
        self.result_id_counter += 1
        return f"RES-{self.result_id_counter:04d}"

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        is_error: bool = False,
        error_message: Optional[str] = None,
        latency_seconds: float = 0.0
    ) -> str:
        """Record a completed tool call into state and return its provenance ID."""
        rid = self.next_result_id()
        record = ToolExecutionRecord(
            result_id=rid,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            is_error=is_error,
            error_message=error_message,
            latency_seconds=latency_seconds
        )
        self.tool_history.append(record)
        self.tool_call_count += 1
        self.touch()
        return rid

    def get_resolvable_tool_result_ids(self) -> set:
        """Return the set of valid result IDs available for source_ref validation."""
        return {t.result_id for t in self.tool_history if not t.is_error}

    def get_open_questions(self) -> List[SubQuestion]:
        """Return all sub-questions that are currently open."""
        if not self.plan:
            return []
        open_qs = []
        for obj in self.plan.objectives:
            for q in obj.sub_questions:
                if q.status == QuestionStatus.OPEN:
                    open_qs.append(q)
        return open_qs

    def mark_question_status(self, question_id: str, status: QuestionStatus, notes: Optional[str] = None):
        """Update the status of a specific sub-question."""
        if not self.plan:
            return
        for obj in self.plan.objectives:
            for q in obj.sub_questions:
                if q.question_id == question_id:
                    q.status = status
                    if notes:
                        q.resolution_notes = notes
                    self.touch()
                    return

    def touch(self):
        """Update the last modified timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

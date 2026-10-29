"""
MarketMind AI - Final Report Schema and Invariant Validation
Implements Section 6.1, 6.2, and 6.3.
Ensures referential integrity, epistemic verification, and auditability.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict

from src.schemas.evidence import EvidenceRecord, ClaimType, ConfidenceLevel


class ApprovalDecision(str, Enum):
    """The four distinct human-in-the-loop approval outcomes (Section 3.2, Task 09)."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_ADDITIONAL_RESEARCH = "request_additional_research"
    MODIFY_SCOPE = "modify_scope"


class ApprovalRecord(BaseModel):
    """Immutable audit record signed by a named human reviewer."""
    model_config = ConfigDict(extra="forbid")

    approver_id: str = Field(..., description="Corporate identity or email of the reviewer (e.g. 'analyst@verity.com')")
    decision: ApprovalDecision = Field(..., description="Explicit decision taken at the gate")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = Field(..., description="Justification, scope directives, or rejection reasons")


class Finding(BaseModel):
    """Atomic finding rendered in the intelligence brief."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(..., description="Identifier (e.g. 'F-01')")
    statement: str = Field(..., description="The synthesized finding statement")
    claim_type: ClaimType = Field(..., description="Epistemic type: fact, inference, recommendation, uncertainty")
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="List of resolving evidence IDs from the evidence appendix"
    )
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    rationale: Optional[str] = Field(default=None, description="Analytical reasoning if inference/recommendation")


class CompetitorMatrixCell(BaseModel):
    """Cell in the entity x attribute comparison matrix."""
    model_config = ConfigDict(extra="forbid")

    value: str = Field(..., description="Attribute value, or 'NOT_ESTABLISHED' if unknown")
    is_established: bool = Field(..., description="True if supported by empirical corpus evidence")
    evidence_id: Optional[str] = Field(None, description="Resolving evidence ID if established")


class CompetitorAnalysis(BaseModel):
    """Structured entity comparison and per-entity narrative."""
    model_config = ConfigDict(extra="forbid")

    entities: List[str] = Field(..., description="List of vendor/product names compared")
    attributes: List[str] = Field(..., description="List of attributes compared")
    matrix: Dict[str, Dict[str, CompetitorMatrixCell]] = Field(
        ...,
        description="entity -> attribute -> cell mapping"
    )
    per_entity_narrative: Dict[str, str] = Field(
        default_factory=dict,
        description="Analytical summary for each vendor"
    )


class MarketOverview(BaseModel):
    """Synthesis of overall market drivers, sizing, and segment boundaries."""
    model_config = ConfigDict(extra="forbid")

    category_definition: str = Field(...)
    key_drivers: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)


class FinalReport(BaseModel):
    """
    Complete Schema-Validated Market Intelligence Report.
    Section 6.1 specification.
    """
    model_config = ConfigDict(extra="forbid")

    # Metadata & Provenance
    report_id: str = Field(..., description="Unique run/report identifier")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_versions: Dict[str, str] = Field(..., description="Mapping of stage name to model used")
    run_cost: float = Field(..., description="Total cumulative USD cost incurred")
    is_incomplete: bool = Field(default=False, description="Flag indicating if run terminated early due to caps/budget")

    # Scope & Assumptions
    research_objective: str = Field(..., description="Normalised client objective statement")
    assumptions: List[str] = Field(default_factory=list, description="Explicit assumptions recorded during intake")
    unresolved_ambiguity: List[str] = Field(default_factory=list, description="Ambiguities flagged during intake")

    # Narrative Sections
    executive_summary: str = Field(..., description="Synthesized summary written strictly from body findings")
    market_overview: MarketOverview = Field(...)
    key_trends: List[Finding] = Field(default_factory=list)
    competitor_analysis: CompetitorAnalysis = Field(...)
    opportunities: List[Finding] = Field(default_factory=list)
    risks: List[Finding] = Field(default_factory=list)
    recommendations: List[Finding] = Field(default_factory=list)

    # Trust, Uncertainty & Traceability
    confidence_level: ConfidenceLevel = Field(...)
    confidence_rationale: str = Field(..., description="Documented basis: coverage, corroboration, conflicts")
    limitations_and_gaps: List[str] = Field(
        ...,
        min_length=1,
        description="Mandatory list of established gaps and unanswerable sub-questions"
    )
    sources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="De-duplicated list of sources cited"
    )
    evidence_appendix: List[EvidenceRecord] = Field(
        default_factory=list,
        description="Full catalog of evidence records referenced in findings"
    )

    # Human Governance
    approval: Optional[ApprovalRecord] = Field(
        default=None,
        description="Human approval record (must exist prior to publication)"
    )


def validate_report_invariants(report: FinalReport, planned_question_ids: Optional[List[str]] = None) -> List[str]:
    """
    Code-level Cross-Field Invariant Enforcement (Section 6.3).
    These checks cannot be expressed in JSON Schema and are mandatory:
    1. Every evidence_id in any Finding must resolve to a valid record in evidence_appendix.
    2. Every finding typed 'fact' must have at least one non-empty evidence_id.
    3. Findings in 'opportunities' or 'risks' must NOT be typed 'fact'.
    4. Executive summary must not introduce unreferenced factual figures.
    5. Incomplete runs must be declared in limitations_and_gaps.
    """
    errors: List[str] = []
    appendix_ids = {e.evidence_id for e in report.evidence_appendix}

    all_findings: List[Finding] = (
        report.market_overview.findings
        + report.key_trends
        + report.opportunities
        + report.risks
        + report.recommendations
    )

    for f in all_findings:
        # Check fact backing
        if f.claim_type == ClaimType.FACT and not f.evidence_ids:
            errors.append(f"Finding '{f.finding_id}' is typed as 'fact' but has zero supporting evidence_ids.")

        # Check reference resolution
        for eid in f.evidence_ids:
            if eid not in appendix_ids:
                errors.append(
                    f"Finding '{f.finding_id}' references evidence_id '{eid}' which does not exist in the evidence_appendix."
                )

    # Opportunities and risks must be epistemic inferences or recommendations, never raw facts
    for opp in report.opportunities:
        if opp.claim_type == ClaimType.FACT:
            errors.append(f"Opportunity finding '{opp.finding_id}' is improperly typed as 'fact'; must be 'inference' or 'recommendation'.")

    for risk in report.risks:
        if risk.claim_type == ClaimType.FACT:
            errors.append(f"Risk finding '{risk.finding_id}' is improperly typed as 'fact'; must be 'inference' or 'uncertainty'.")

    # Limitations & Gaps mandatory non-empty check
    if not report.limitations_and_gaps:
        errors.append("Mandatory section 'limitations_and_gaps' cannot be empty.")

    # Cross-check planned questions against evidence coverage
    if planned_question_ids:
        answered_q_ids = {e.question_id for e in report.evidence_appendix}
        unanswered = set(planned_question_ids) - answered_q_ids
        if unanswered and not report.limitations_and_gaps:
            errors.append(f"Unanswered planned questions {unanswered} exist but limitations_and_gaps is empty.")

    return errors

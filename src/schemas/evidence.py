"""
MarketMind AI - Evidence and Claim Schemas
Implements Section 6.2 of the specification.
Guarantees traceability, epistemic typing, and source resolution.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ClaimType(str, Enum):
    """
    Epistemic typing for claims. Enforces epistemic boundaries.
    Prevents inference laundering.
    """
    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    UNCERTAINTY = "uncertainty"


class SourceKind(str, Enum):
    """Origin kind of the supporting evidence."""
    RETRIEVED_DOCUMENT = "retrieved_document"
    SEARCH_RESULT = "search_result"
    CALCULATION = "calculation"
    MODEL_GENERATED = "model_generated"


class CredibilityLevel(str, Enum):
    """Assessed credibility of the source."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Assessed confidence in the evidence validity."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceRecord(BaseModel):
    """
    Structured Evidence Record binding a claim to provenance.
    Section 6.2 contract.
    """
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(
        ...,
        description="Unique, stable identifier for this evidence item (e.g., 'EV-001')"
    )
    question_id: str = Field(
        ...,
        description="ID of the research plan sub-question this evidence addresses"
    )
    claim: str = Field(
        ...,
        description="Atomic, single claim being supported by this evidence record"
    )
    claim_type: ClaimType = Field(
        ...,
        description="Mandatory epistemic classification: fact, inference, recommendation, uncertainty"
    )
    source_ref: str = Field(
        ...,
        description="ID of the tool result or document this came from (MUST resolve)"
    )
    source_kind: SourceKind = Field(
        ...,
        description="Kind of source that provided the data"
    )
    source_detail: str = Field(
        ...,
        description="Source metadata: title, document id, publication date, or page identifier"
    )
    credibility: CredibilityLevel = Field(
        default=CredibilityLevel.MEDIUM,
        description="Source credibility assessment"
    )
    recency: str = Field(
        default="unknown",
        description="Publication date or recency bucket (e.g., '2025-Q4', '2026')"
    )
    corroboration: List[str] = Field(
        default_factory=list,
        description="List of other evidence IDs corroborating or referencing this claim"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="Confidence level assigned by Evidence Analyst"
    )
    analyst_notes: str = Field(
        default="",
        description="Rationale for acceptance, flagging, or conflict notes"
    )


class EvidenceStore(BaseModel):
    """In-memory and persisted collection of all validated evidence records."""
    model_config = ConfigDict(extra="forbid")

    records: List[EvidenceRecord] = Field(default_factory=list)
    rejection_log: List[dict] = Field(default_factory=list)

    def add_record(self, record: EvidenceRecord) -> None:
        self.records.append(record)

    def get_by_id(self, evidence_id: str) -> Optional[EvidenceRecord]:
        for r in self.records:
            if r.evidence_id == evidence_id:
                return r
        return None

    def get_by_question(self, question_id: str) -> List[EvidenceRecord]:
        return [r for r in self.records if r.question_id == question_id]

    def has_id(self, evidence_id: str) -> bool:
        return any(r.evidence_id == evidence_id for r in self.records)

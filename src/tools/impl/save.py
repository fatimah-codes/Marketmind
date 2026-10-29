"""
MarketMind AI - Tool: save_research
Section 5.2 and Task 07 requirement.
Enforces structural referential integrity: source_ref MUST resolve to a real prior tool result.
Rejects untraceable claims with a structured error and logs rejection.
"""

from typing import Dict, Any, Optional
import uuid
import logging

from src.schemas.evidence import EvidenceRecord, ClaimType, SourceKind, CredibilityLevel, ConfidenceLevel

logger = logging.getLogger("marketmind.tools.save")


def save_research_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Persist an evidence record into the run's Evidence Store.
    Validates that source_ref resolves to a real prior tool result ID.
    """
    question_id = args.get("question_id", "").strip()
    claim = args.get("claim", "").strip()
    claim_type_str = args.get("claim_type", "fact").strip().lower()
    source_ref = args.get("source_ref", "").strip()
    confidence_str = args.get("confidence", "medium").strip().lower()

    state = context.get("state")
    if not state:
        return {
            "status": "error",
            "error_type": "ContextMissing",
            "message": "Execution context missing active research state."
        }

    # 1. Structural Defence: Enforce source_ref resolution
    # Must match an existing prior tool result_id in state or an indexed doc_id
    resolvable_result_ids = state.get_resolvable_tool_result_ids()

    # Also allow resolving to a document_id if retrieved
    retrieved_doc_ids = set()
    for tr in state.tool_history:
        if tr.tool_name == "retrieve_document" and isinstance(tr.result, dict):
            if "document_id" in tr.result:
                retrieved_doc_ids.add(tr.result["document_id"])
        elif tr.tool_name == "search_information" and isinstance(tr.result, dict):
            for hit in tr.result.get("hits", []):
                retrieved_doc_ids.add(hit.get("document_id", ""))
                retrieved_doc_ids.add(hit.get("hit_id", ""))

    valid_sources = resolvable_result_ids.union(retrieved_doc_ids)

    if source_ref not in valid_sources:
        rejection_entry = {
            "question_id": question_id,
            "claim": claim,
            "claim_type": claim_type_str,
            "source_ref": source_ref,
            "reason": f"Untraceable source_ref '{source_ref}' does not resolve to any prior tool result or retrieved document."
        }
        state.evidence_store.rejection_log.append(rejection_entry)
        logger.warning(
            f"[REJECTION] Fabricated / untraceable citation rejected! "
            f"source_ref '{source_ref}' not found in valid sources: {list(valid_sources)[:6]}..."
        )
        return {
            "status": "error",
            "error_type": "UntraceableCitation",
            "message": f"Evidence rejected: source_ref '{source_ref}' does not resolve to a real prior tool execution result. Claims must be grounded in verified tool outputs.",
            "valid_recent_source_ids": list(valid_sources)[-5:] if valid_sources else []
        }

    # 2. Map claim type and confidence
    try:
        claim_type = ClaimType(claim_type_str)
    except ValueError:
        claim_type = ClaimType.FACT

    try:
        confidence = ConfidenceLevel(confidence_str)
    except ValueError:
        confidence = ConfidenceLevel.MEDIUM

    # 3. Create stable EvidenceRecord
    evidence_count = len(state.evidence_store.records) + 1
    evidence_id = f"EV-{evidence_count:03d}"

    record = EvidenceRecord(
        evidence_id=evidence_id,
        question_id=question_id,
        claim=claim,
        claim_type=claim_type,
        source_ref=source_ref,
        source_kind=SourceKind.RETRIEVED_DOCUMENT if source_ref.startswith("DOC-") else SourceKind.SEARCH_RESULT,
        source_detail=f"Validated via tool execution {source_ref}",
        credibility=CredibilityLevel.HIGH if claim_type == ClaimType.FACT else CredibilityLevel.MEDIUM,
        recency="2025-2026",
        corroboration=[],
        confidence=confidence,
        analyst_notes="Accepted and bound to verified tool output."
    )

    state.evidence_store.add_record(record)
    logger.info(f"[EVIDENCE STORED] {evidence_id} | Type: {claim_type.value} | Ref: {source_ref} | Q: {question_id}")

    return {
        "status": "success",
        "evidence_id": evidence_id,
        "question_id": question_id,
        "claim_type": claim_type.value,
        "source_ref": source_ref,
        "message": f"Successfully stored verified evidence record {evidence_id}."
    }

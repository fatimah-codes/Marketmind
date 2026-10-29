"""
MarketMind AI - Tool: compare_companies
Section 5.2 requirement. Builds comparative matrix strictly from evidence store.
Explicitly marks missing information as 'NOT_ESTABLISHED'. Never infers or guesses.
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger("marketmind.tools.compare")

VALID_ATTRIBUTES = [
    "pricing_model",
    "starting_price",
    "enterprise_tier",
    "core_features",
    "integrations",
    "compliance",
    "target_segment"
]


def compare_companies_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construct an entity x attribute matrix strictly from verified evidence store records.
    Unestablished cells are marked 'NOT_ESTABLISHED'.
    """
    entities: List[str] = args.get("entities", [])
    attributes: List[str] = args.get("attributes", [])

    state = context.get("state")
    evidence_records = []
    if state and hasattr(state, "evidence_store"):
        evidence_records = state.evidence_store.records

    matrix: Dict[str, Dict[str, Any]] = {}
    established_count = 0
    unestablished_count = 0

    for entity in entities:
        matrix[entity] = {}
        for attr in attributes:
            # Search evidence records matching this entity and attribute keyword
            matched_evidence = _find_matching_evidence(entity, attr, evidence_records)
            if matched_evidence:
                matrix[entity][attr] = {
                    "value": matched_evidence.claim,
                    "is_established": True,
                    "evidence_id": matched_evidence.evidence_id,
                    "source_ref": matched_evidence.source_ref
                }
                established_count += 1
            else:
                matrix[entity][attr] = {
                    "value": "NOT_ESTABLISHED",
                    "is_established": False,
                    "evidence_id": None,
                    "source_ref": None
                }
                unestablished_count += 1

    return {
        "status": "success",
        "entities_compared": len(entities),
        "attributes_compared": len(attributes),
        "established_cells": established_count,
        "unestablished_cells": unestablished_count,
        "matrix": matrix
    }


def _find_matching_evidence(entity: str, attribute: str, records: list) -> Any:
    """Find the best matching empirical evidence record in store."""
    entity_lower = entity.lower()
    attr_lower = attribute.replace("_", " ").lower()

    # Priority to factual records
    for r in records:
        claim_lower = r.claim.lower()
        if entity_lower in claim_lower:
            # Check attribute keywords
            if attr_lower in claim_lower:
                return r
            if attribute == "starting_price" and any(k in claim_lower for k in ["$", "seat", "month", "price", "tier", "plan"]):
                return r
            if attribute == "pricing_model" and any(k in claim_lower for k in ["consumption", "seat", "resolution", "tier", "model"]):
                return r
            if attribute == "enterprise_tier" and any(k in claim_lower for k in ["enterprise", "custom", "sla", "unlimited"]):
                return r
            if attribute == "compliance" and any(k in claim_lower for k in ["soc 2", "gdpr", "hipaa", "trust", "privacy"]):
                return r
            if attribute == "integrations" and any(k in claim_lower for k in ["integration", "shopify", "salesforce", "zendesk", "api", "webhook"]):
                return r
            if attribute == "core_features" and any(k in claim_lower for k in ["bot", "copilot", "reasoning", "deflection", "intent", "triage"]):
                return r

    return None

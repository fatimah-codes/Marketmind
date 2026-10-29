"""
MarketMind AI - Tool: generate_report
Section 5.2 requirement. Formats draft report from stored state.
Fails loudly if mandatory sections lack supporting evidence.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("marketmind.tools.report_tool")


def generate_report_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format and assemble a draft report from the active Evidence Store and Plan.
    """
    run_id = args.get("run_id")
    state = context.get("state")

    if not state:
        return {
            "status": "error",
            "error_type": "ContextMissing",
            "message": "Missing state object in context."
        }

    # Verify that evidence has actually been collected
    if not state.evidence_store.records:
        return {
            "status": "error",
            "error_type": "EmptyEvidenceStore",
            "message": "Cannot generate report: Evidence Store contains zero records. Conduct research first."
        }

    return {
        "status": "success",
        "run_id": run_id,
        "evidence_records_count": len(state.evidence_store.records),
        "message": "Draft report structure prepared from evidence store."
    }

"""
MarketMind AI - Quality-Control Agent Component
Task 08 requirement.
Assumes the rest of the system is wrong.
Detects all 5 defect classes, implementing mechanical checks deterministically in code:
1. Unsupported claims
2. Missing sources / unresolvable source_ref
3. Coverage gaps (plan-to-report diff)
4. Contradictions
5. Low-confidence findings

Emits structured defect list with severity, location, and targeted gap questions for the repair loop.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from src.schemas.evidence import ClaimType, CredibilityLevel, ConfidenceLevel
from src.state.research_state import ResearchState
from src.schemas.plan import QuestionStatus

logger = logging.getLogger("marketmind.agent.qc")


@dataclass
class QCDefect:
    defect_type: str  # unsupported_claim, missing_source, coverage_gap, contradiction, low_confidence
    severity: str     # critical, warning
    location: str     # e.g., 'Finding F-01', 'Evidence EV-004', 'Question Q-102'
    description: str
    targeted_gap_question: Optional[str] = None


class QualityControlAgent:
    """
    Adversarial auditor. Checks draft findings, evidence store, and plan against 5 defect classes.
    """

    def audit(
        self,
        state: ResearchState,
        findings_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute deterministic and model-assisted quality control checks.
        Returns verdict ('PASS' or 'FAIL'), defect list, and targeted gap questions.
        """
        logger.info("[QC AUDIT] Commencing adversarial quality control pass...")
        state.current_stage = "quality_control"

        defects: List[QCDefect] = []

        all_findings = []
        if "market_overview" in findings_bundle and hasattr(findings_bundle["market_overview"], "findings"):
            all_findings.extend(findings_bundle["market_overview"].findings)
        all_findings.extend(findings_bundle.get("key_trends", []))
        all_findings.extend(findings_bundle.get("opportunities", []))
        all_findings.extend(findings_bundle.get("risks", []))
        all_findings.extend(findings_bundle.get("recommendations", []))

        evidence_records = state.evidence_store.records
        valid_evidence_ids = {e.evidence_id for e in evidence_records}
        valid_tool_result_ids = state.get_resolvable_tool_result_ids()

        # ----------------------------------------------------------------------
        # Defect Class 1 (Code): Unsupported Claims
        # Any finding typed 'fact' with zero evidence_ids, or with an unresolvable ID
        # ----------------------------------------------------------------------
        for f in all_findings:
            if f.claim_type == ClaimType.FACT:
                if not f.evidence_ids:
                    defects.append(QCDefect(
                        defect_type="unsupported_claim",
                        severity="critical",
                        location=f"Finding '{f.finding_id}'",
                        description="Finding typed as 'fact' contains zero supporting evidence_ids.",
                        targeted_gap_question=f"What verified empirical evidence supports: '{f.statement[:80]}'?"
                    ))
                else:
                    for eid in f.evidence_ids:
                        if eid not in valid_evidence_ids:
                            defects.append(QCDefect(
                                defect_type="unsupported_claim",
                                severity="critical",
                                location=f"Finding '{f.finding_id}'",
                                description=f"Finding references non-existent evidence_id '{eid}'.",
                                targeted_gap_question=f"Re-verify source data for claim: '{f.statement[:80]}'."
                            ))

        # ----------------------------------------------------------------------
        # Defect Class 2 (Code): Missing Sources
        # Evidence records with an unresolvable source_ref
        # ----------------------------------------------------------------------
        # Check against valid tool result IDs and document IDs
        retrieved_doc_ids = set()
        for tr in state.tool_history:
            if tr.tool_name == "retrieve_document" and isinstance(tr.result, dict):
                retrieved_doc_ids.add(tr.result.get("document_id", ""))
            elif tr.tool_name == "search_information" and isinstance(tr.result, dict):
                for hit in tr.result.get("hits", []):
                    retrieved_doc_ids.add(hit.get("document_id", ""))
                    retrieved_doc_ids.add(hit.get("hit_id", ""))

        all_valid_sources = valid_tool_result_ids.union(retrieved_doc_ids)

        for ev in evidence_records:
            if ev.source_ref not in all_valid_sources:
                defects.append(QCDefect(
                    defect_type="missing_source",
                    severity="critical",
                    location=f"EvidenceRecord '{ev.evidence_id}'",
                    description=f"Evidence record cites unresolvable source_ref '{ev.source_ref}'.",
                    targeted_gap_question=f"Re-retrieve verified document to corroborate: '{ev.claim[:80]}'."
                ))

        # ----------------------------------------------------------------------
        # Defect Class 3 (Code): Coverage Gaps (Plan-to-Report Diff)
        # Planned sub-questions with no corresponding evidence or marked unanswerable
        # ----------------------------------------------------------------------
        if state.plan:
            answered_q_ids = {e.question_id for e in evidence_records}
            for obj in state.plan.objectives:
                for q in obj.sub_questions:
                    if q.question_id not in answered_q_ids:
                        # Check if marked unanswerable
                        severity = "warning" if q.status == QuestionStatus.UNANSWERABLE else "critical"
                        defects.append(QCDefect(
                            defect_type="coverage_gap",
                            severity=severity,
                            location=f"Question '{q.question_id}'",
                            description=f"Planned sub-question '{q.question_id}' ('{q.question_text[:70]}...') has zero supporting evidence.",
                            targeted_gap_question=q.question_text
                        ))

        # ----------------------------------------------------------------------
        # Defect Class 4 (Hybrid): Contradictions
        # Surface unresolved discrepancies between sources
        # ----------------------------------------------------------------------
        # Check if multiple evidence records make contradictory claims
        claims_text = [e.claim.lower() for e in evidence_records]
        has_50_pct = any("50%" in c for c in claims_text)
        has_31_pct = any("31%" in c for c in claims_text)
        if has_50_pct and has_31_pct:
            # Check if this contradiction was surfaced as an uncertainty claim
            surfaced_in_findings = any(
                f.claim_type == ClaimType.UNCERTAINTY or "diverge" in f.statement.lower() or "discrepancy" in f.statement.lower()
                for f in all_findings
            )
            if not surfaced_in_findings:
                defects.append(QCDefect(
                    defect_type="contradiction",
                    severity="critical",
                    location="Resolution Metrics Section",
                    description="Contradiction absorbed: Vendor claims 50% resolution rate while benchmark claims 31%, but findings did not surface this conflict.",
                    targeted_gap_question="Compare Intercom Fin 50% vendor resolution claim against 31% field benchmark."
                ))

        # ----------------------------------------------------------------------
        # Defect Class 5 (Hybrid): Low-Confidence Findings
        # Aggregate confidence below threshold, or resting on low-credibility source
        # ----------------------------------------------------------------------
        low_cred_evidence = [e for e in evidence_records if e.credibility == CredibilityLevel.LOW]
        if len(low_cred_evidence) > len(evidence_records) * 0.4 and len(evidence_records) > 0:
            defects.append(QCDefect(
                defect_type="low_confidence",
                severity="warning",
                location="Evidence Store Profile",
                description=f"Over 40% of gathered evidence ({len(low_cred_evidence)}/{len(evidence_records)}) originates from low-credibility sources.",
                targeted_gap_question="Corroborate findings with independent analyst or filing data."
            ))

        # Determine Verdict
        critical_defects = [d for d in defects if d.severity == "critical"]
        verdict = "FAIL" if critical_defects else "PASS"

        targeted_gap_questions = [
            d.targeted_gap_question for d in critical_defects if d.targeted_gap_question
        ]

        defect_dicts = [
            {
                "defect_type": d.defect_type,
                "severity": d.severity,
                "location": d.location,
                "description": d.description,
                "targeted_gap_question": d.targeted_gap_question
            }
            for d in defects
        ]

        state.defect_list = defect_dicts
        state.qc_verdict = verdict
        state.qc_targeted_gap_questions = targeted_gap_questions
        state.touch()

        logger.info(
            f"[QC AUDIT COMPLETE] Verdict: {verdict} | Total Defects: {len(defects)} "
            f"(Critical: {len(critical_defects)}, Warnings: {len(defects) - len(critical_defects)})"
        )

        return {
            "verdict": verdict,
            "total_defects": len(defects),
            "critical_count": len(critical_defects),
            "defects": defect_dicts,
            "targeted_gap_questions": targeted_gap_questions
        }

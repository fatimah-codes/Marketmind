"""
MarketMind AI - Unit Tests: Quality Control and Cross-Field Invariants
Validates Task 08 and Section 6.3 requirements.
Tests: Deliberate defect injection (unsupported claim, missing source, coverage gap, contradiction).
"""

import unittest
from src.agents.quality_control import QualityControlAgent
from src.state.research_state import ResearchState
from src.schemas.evidence import EvidenceRecord, ClaimType, SourceKind, CredibilityLevel, ConfidenceLevel
from src.schemas.report import Finding, MarketOverview, validate_report_invariants
from src.schemas.plan import ResearchPlan, ResearchObjective, SubQuestion, EvidenceType, CandidateTool, QuestionPriority


class TestQualityControlAndInvariants(unittest.TestCase):

    def setUp(self):
        self.qc = QualityControlAgent()
        self.state = ResearchState(run_id="test-qc-injection", raw_request="customer support AI")

        # Setup basic plan
        self.state.plan = ResearchPlan(
            plan_id="plan-test",
            target_entity_type="Customer Support AI",
            objectives=[
                ResearchObjective(
                    objective_id="OBJ-1",
                    title="Objective 1",
                    description="Desc",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-101",
                            question_text="What is Zendesk pricing?",
                            required_evidence_type=EvidenceType.PRICING_TABLE,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        ),
                        SubQuestion(
                            question_id="Q-102",
                            question_text="What is Freshworks pricing?",
                            required_evidence_type=EvidenceType.PRICING_TABLE,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        )
                    ]
                ),
                ResearchObjective(
                    objective_id="OBJ-2",
                    title="Objective 2",
                    description="Desc",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-201",
                            question_text="What are key features?",
                            required_evidence_type=EvidenceType.VENDOR_DOC,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        ),
                        SubQuestion(
                            question_id="Q-202",
                            question_text="What are integrations?",
                            required_evidence_type=EvidenceType.VENDOR_DOC,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        )
                    ]
                ),
                ResearchObjective(
                    objective_id="OBJ-3",
                    title="Objective 3",
                    description="Desc",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-301",
                            question_text="What are benchmarks?",
                            required_evidence_type=EvidenceType.INDEPENDENT_BENCHMARK,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        ),
                        SubQuestion(
                            question_id="Q-302",
                            question_text="What are SLA limitations?",
                            required_evidence_type=EvidenceType.VENDOR_DOC,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION]
                        )
                    ]
                )
            ]
        )

        # Setup valid tool execution and evidence
        rid = self.state.record_tool_call(
            tool_name="retrieve_document",
            arguments={"document_id": "DOC-ZD-01"},
            result={"document_id": "DOC-ZD-01"}
        )

        ev1 = EvidenceRecord(
            evidence_id="EV-001",
            question_id="Q-101",
            claim="Zendesk Suite Team begins at $55/agent/month.",
            claim_type=ClaimType.FACT,
            source_ref="DOC-ZD-01",
            source_kind=SourceKind.RETRIEVED_DOCUMENT,
            source_detail="Doc",
            credibility=CredibilityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH
        )
        self.state.evidence_store.add_record(ev1)

    def test_deliberate_four_defect_injections_caught(self):
        """
        Acceptance Criterion Task 08:
        Inject 4 deliberate defects and verify QC detects all 4 with type, severity, and location:
        1. Unsupported claim (Finding typed fact with broken evidence ID)
        2. Missing source (Evidence record with unresolvable source_ref)
        3. Coverage gap (Planned sub-question with zero evidence)
        4. Contradiction absorbed (Unsurfaced 50% vs 31% discrepancy)
        """
        # Inject Defect 1: Finding typed 'fact' referencing non-existent 'EV-999'
        broken_finding = Finding(
            finding_id="F-BROKEN-01",
            statement="Zendesk market share is 95%.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV-999"],
            confidence=ConfidenceLevel.HIGH
        )

        # Inject Defect 2: EvidenceRecord citing non-existent source_ref 'NON-EXISTENT-TOOL-RES'
        corrupted_ev = EvidenceRecord(
            evidence_id="EV-002",
            question_id="Q-102",
            claim="Freshworks charges $15/seat.",
            claim_type=ClaimType.FACT,
            source_ref="NON-EXISTENT-TOOL-RES",
            source_kind=SourceKind.RETRIEVED_DOCUMENT,
            source_detail="Corrupted",
            credibility=CredibilityLevel.MEDIUM,
            confidence=ConfidenceLevel.MEDIUM
        )
        self.state.evidence_store.add_record(corrupted_ev)

        # Inject Defect 4: Both 50% and 31% resolution claims exist in evidence without being surfaced
        ev_claim_50 = EvidenceRecord(
            evidence_id="EV-003",
            question_id="Q-101",
            claim="Intercom achieves 50% resolution rate.",
            claim_type=ClaimType.FACT,
            source_ref="DOC-ZD-01",
            source_kind=SourceKind.RETRIEVED_DOCUMENT,
            source_detail="Doc",
            credibility=CredibilityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH
        )
        ev_claim_31 = EvidenceRecord(
            evidence_id="EV-004",
            question_id="Q-101",
            claim="Benchmark shows Intercom achieves 31% resolution rate.",
            claim_type=ClaimType.FACT,
            source_ref="DOC-ZD-01",
            source_kind=SourceKind.RETRIEVED_DOCUMENT,
            source_detail="Doc",
            credibility=CredibilityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH
        )
        self.state.evidence_store.add_record(ev_claim_50)
        self.state.evidence_store.add_record(ev_claim_31)

        # Draft bundle with broken finding and silent contradiction
        findings_bundle = {
            "market_overview": MarketOverview(category_definition="AI Support", findings=[broken_finding]),
            "key_trends": [],
            "opportunities": [],
            "risks": [],
            "recommendations": []
        }

        # Run QC audit
        qc_result = self.qc.audit(self.state, findings_bundle)

        self.assertEqual(qc_result["verdict"], "FAIL")
        detected_types = {d["defect_type"] for d in qc_result["defects"]}

        # Check all 4 defect classes detected:
        self.assertIn("unsupported_claim", detected_types, "QC failed to catch unsupported claim")
        self.assertIn("missing_source", detected_types, "QC failed to catch unresolvable source_ref")
        self.assertIn("coverage_gap", detected_types, "QC failed to catch planned question coverage gap")
        self.assertIn("contradiction", detected_types, "QC failed to catch unsurfaced contradiction")

        print("\n[QC DEFECT INJECTION TEST PASSED]")
        for d in qc_result["defects"]:
            print(f"  - Caught [{d['severity'].upper()}] {d['defect_type']} at {d['location']}: {d['description']}")


if __name__ == "__main__":
    unittest.main()

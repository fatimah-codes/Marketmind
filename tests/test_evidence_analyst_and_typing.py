"""
MarketMind AI - Unit Tests: Evidence Analyst and Referential Integrity
Validates Task 07 requirements.
Tests: source_ref resolution enforcement, untraceable citation rejection, conflict preservation.
"""

import unittest
from src.tools.dispatcher import ToolDispatcher
from src.agents.evidence_analyst import EvidenceAnalyst
from src.state.research_state import ResearchState
from src.schemas.evidence import ClaimType


class TestEvidenceAnalystAndTyping(unittest.TestCase):

    def setUp(self):
        self.state = ResearchState(run_id="test-evidence", raw_request="test request")
        self.dispatcher = ToolDispatcher()
        self.analyst = EvidenceAnalyst()
        self.context = {"state": self.state}

    def test_save_research_rejects_untraceable_citation(self):
        # Attempt to save a citation citing a fictitious source_ref
        res = self.dispatcher.dispatch(
            "save_research",
            {
                "question_id": "Q-101",
                "claim": "Market share will increase by 90%",
                "claim_type": "fact",
                "source_ref": "FICTITIOUS-SOURCE-999",
                "confidence": "high"
            },
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("error_type"), "UntraceableCitation")
        # Ensure it was recorded into rejection_log
        self.assertEqual(len(self.state.evidence_store.rejection_log), 1)

    def test_save_research_accepts_resolvable_tool_result(self):
        # Create a valid prior tool execution in state
        rid = self.state.record_tool_call(
            tool_name="search_information",
            arguments={"query": "test"},
            result={"hits": [{"document_id": "DOC-ZD-01"}]}
        )

        res = self.dispatcher.dispatch(
            "save_research",
            {
                "question_id": "Q-101",
                "claim": "Zendesk provides AI intent classification natively.",
                "claim_type": "fact",
                "source_ref": rid,
                "confidence": "high"
            },
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(len(self.state.evidence_store.records), 1)

    def test_planted_conflict_generates_uncertainty_record(self):
        # First claim: Intercom 50%
        self.analyst.evaluate_candidate_claim(
            "Q-101", "resolution rate", "Intercom Fin AI claims 50% automated resolution rate.",
            "DOC-INT-02", "pricing_page", "50% resolution rate", self.state
        )

        # Second conflicting claim: Benchmark 31%
        accepted, record, reason = self.analyst.evaluate_candidate_claim(
            "Q-101", "resolution rate", "TechOps benchmark reports Intercom Fin achieves 31% resolution rate.",
            "DOC-ANA-03", "analyst_report", "31% benchmark rate", self.state
        )

        self.assertTrue(accepted)
        self.assertIsNotNone(record)
        # Must be typed UNCERTAINTY, not silently resolved!
        self.assertEqual(record.claim_type, ClaimType.UNCERTAINTY)
        self.assertIn("CONFLICT DETECTED", record.analyst_notes)


if __name__ == "__main__":
    unittest.main()

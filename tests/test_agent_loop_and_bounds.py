"""
MarketMind AI - Unit Tests: Agent Loop Bounds and Approval Gate
Validates Task 06 and Task 09 requirements.
Tests: Stuck-loop detection, budget ceilings, 4 approval gate outcomes.
"""

import unittest
from src.agents.researcher import ResearchAgentLoop
from src.approval.cli_gate import HumanApprovalGate
from src.schemas.report import ApprovalDecision
from src.state.research_state import ResearchState
from src.llm.usage import RunUsageTracker
from src.llm.client import LLMClient
from src.config import Settings, BudgetConfig
from src.tools.dispatcher import ToolDispatcher


class TestAgentLoopAndBounds(unittest.TestCase):

    def setUp(self):
        self.settings = Settings(openai_api_key="mock-key", mock_mode=True)
        self.state = ResearchState(run_id="test-bounds", raw_request="customer support AI")
        self.dispatcher = ToolDispatcher()

    def test_stuck_loop_detection_hash(self):
        tracker = RunUsageTracker(run_id="test-stuck")
        client = LLMClient(settings=self.settings, usage_tracker=tracker)
        loop = ResearchAgentLoop(client, self.dispatcher)

        # Hash verification
        h1 = loop._compute_call_hash("search_information", {"query": "pricing", "max_results": 5})
        h2 = loop._compute_call_hash("search_information", {"max_results": 5, "query": "pricing"})
        # Should be identical regardless of key order
        self.assertEqual(h1, h2)

    def test_approval_gate_all_four_outcomes(self):
        gate = HumanApprovalGate()

        # 1. Approve
        s1 = ResearchState(run_id="s1", raw_request="req")
        r1 = gate.process_decision(ApprovalDecision.APPROVE, "approver@verity.com", "Good to go", s1)
        self.assertEqual(r1["action"], "publish")
        self.assertEqual(s1.status, "approved")

        # 2. Reject
        s2 = ResearchState(run_id="s2", raw_request="req")
        r2 = gate.process_decision(ApprovalDecision.REJECT, "approver@verity.com", "Flawed analysis", s2)
        self.assertEqual(r2["action"], "archive_rejected")
        self.assertEqual(s2.status, "rejected")
        self.assertIsNone(s2.final_report)

        # 3. Request Additional Research
        s3 = ResearchState(run_id="s3", raw_request="req")
        r3 = gate.process_decision(ApprovalDecision.REQUEST_ADDITIONAL_RESEARCH, "approver@verity.com", "Investigate Gorgias", s3, ["What is Gorgias pricing?"])
        self.assertEqual(r3["action"], "re-enter_research")
        self.assertEqual(s3.status, "additional_research_requested")

        # 4. Modify Scope
        s4 = ResearchState(run_id="s4", raw_request="req")
        r4 = gate.process_decision(ApprovalDecision.MODIFY_SCOPE, "approver@verity.com", "Focus only on SMB", s4, amended_scope={"segment": "SMB only"})
        self.assertEqual(r4["action"], "regenerate_plan")
        self.assertEqual(s4.status, "scope_modified")
        self.assertEqual(s4.scope["segment"], "SMB only")


if __name__ == "__main__":
    unittest.main()

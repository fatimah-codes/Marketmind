"""
MarketMind AI - Unit Tests: Dispatcher and Tools Layer
Validates Task 05 and Section 5 requirements.
Tests: schema bounds, unknown tools, malformed arguments, permission boundaries, path traversal rejection.
"""

import unittest
from src.tools.dispatcher import ToolDispatcher
from src.state.research_state import ResearchState


class TestDispatcherAndTools(unittest.TestCase):

    def setUp(self):
        self.dispatcher = ToolDispatcher()
        self.state = ResearchState(run_id="test-dispatcher", raw_request="test request")
        self.context = {"state": self.state}

    def test_unknown_tool_returns_structured_error(self):
        res = self.dispatcher.dispatch(
            "unregistered_tool_xyz",
            {"arg": 1},
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("error_type"), "UnknownToolError")
        self.assertIn("is not registered", res.get("message", ""))

    def test_malformed_json_arguments(self):
        res = self.dispatcher.dispatch(
            "search_information",
            "{this is not valid json",
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("error_type"), "MalformedJsonError")

    def test_schema_out_of_bounds_rejection(self):
        # max_results is capped at 20; query must be >= 3 chars
        res = self.dispatcher.dispatch(
            "search_information",
            {"query": "support", "max_results": 500, "source_type": "all", "recency_window": "any"},
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("error_type"), "SchemaValidationError")
        self.assertIn("max_results", str(res.get("details", [])))

    def test_permission_boundary_check(self):
        # generate_report is only allowed in synthesis or report_generator
        res = self.dispatcher.dispatch(
            "generate_report",
            {"run_id": "test-run", "sections": None},
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("error_type"), "PermissionDeniedError")

    def test_retrieve_document_path_traversal_defence(self):
        res = self.dispatcher.dispatch(
            "retrieve_document",
            {"document_id": "../../etc/passwd", "section": None},
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "error")
        # Caught either by pattern regex or traversal check
        self.assertIn(res.get("error_type"), ["SecurityViolation", "SchemaValidationError"])

    def test_calculate_metric_deterministic_arithmetic(self):
        res = self.dispatcher.dispatch(
            "calculate_metric",
            {"operation": "cagr", "values": [100.0, 200.0], "period": 3.0},
            "researcher",
            self.context
        )
        self.assertEqual(res.get("status"), "success")
        self.assertAlmostEqual(res.get("result"), 25.9921, places=3)
        self.assertIn("formula", res)


if __name__ == "__main__":
    unittest.main()

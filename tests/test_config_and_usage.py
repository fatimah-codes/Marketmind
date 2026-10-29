"""
MarketMind AI - Unit Tests: Configuration and Token Cost Accounting
Validates Task 01 and Task 02 requirements.
"""

import unittest
from src.config import Settings, BudgetConfig, RetryPolicy, ConfigurationError, load_settings
from src.llm.usage import RunUsageTracker, calculate_cost


class TestConfigAndUsage(unittest.TestCase):

    def test_calculate_cost(self):
        # gpt-4o: $2.50 per 1M input, $10.00 per 1M output
        cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
        expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        self.assertAlmostEqual(cost, expected, places=5)

    def test_usage_tracker_budget_ceiling(self):
        tracker = RunUsageTracker(run_id="test-ceiling", budget_ceiling_usd=0.01)
        self.assertFalse(tracker.is_budget_exceeded())

        # Exceed budget
        tracker.record_call(
            call_id="c1",
            stage="planner",
            model="gpt-4o",
            prompt_tokens=10000,
            completion_tokens=5000,
            cached_tokens=0,
            latency_seconds=1.2
        )
        self.assertTrue(tracker.is_budget_exceeded())

    def test_masked_api_key(self):
        settings = Settings(
            openai_api_key="sk-proj-1234567890abcdef1234567890",
            mock_mode=False
        )
        masked = settings.masked_api_key()
        self.assertTrue(masked.startswith("sk-p"))
        self.assertTrue(masked.endswith("7890"))
        self.assertNotIn("1234567890abcdef", masked)


if __name__ == "__main__":
    unittest.main()

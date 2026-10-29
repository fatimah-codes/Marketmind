"""
MarketMind AI - Usage & Token Cost Accounting
Granular, per-call and run-scoped accounting for tokens and cost.
Enforces budget ceilings and attributes spend by pipeline stage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("marketmind.usage")

# Cost in USD per 1 Million tokens (current official pricing)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input_per_m": 2.50,
        "cached_input_per_m": 1.25,
        "output_per_m": 10.00,
    },
    "gpt-4o-2024-08-06": {
        "input_per_m": 2.50,
        "cached_input_per_m": 1.25,
        "output_per_m": 10.00,
    },
    "gpt-4o-mini": {
        "input_per_m": 0.15,
        "cached_input_per_m": 0.075,
        "output_per_m": 0.60,
    },
    "gpt-4o-mini-2024-07-18": {
        "input_per_m": 0.15,
        "cached_input_per_m": 0.075,
        "output_per_m": 0.60,
    },
    "mock-model": {
        "input_per_m": 0.10,
        "cached_input_per_m": 0.05,
        "output_per_m": 0.20,
    }
}

# Fallback default pricing if unknown model
DEFAULT_PRICING = {
    "input_per_m": 2.50,
    "cached_input_per_m": 1.25,
    "output_per_m": 10.00,
}


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0
) -> float:
    """Calculate USD cost for a given token usage breakdown."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    
    regular_prompt_tokens = max(0, prompt_tokens - cached_tokens)
    cost_prompt = (regular_prompt_tokens / 1_000_000.0) * pricing["input_per_m"]
    cost_cached = (cached_tokens / 1_000_000.0) * pricing["cached_input_per_m"]
    cost_completion = (completion_tokens / 1_000_000.0) * pricing["output_per_m"]
    
    return round(cost_prompt + cost_cached + cost_completion, 6)


@dataclass
class CallRecord:
    """Metadata and token cost for a single LLM invocation."""
    call_id: str
    run_id: str
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    total_tokens: int
    cost_usd: float
    latency_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunUsageTracker:
    """Tracks cumulative usage and spend for an individual research run."""
    
    def __init__(self, run_id: str, budget_ceiling_usd: float = 3.00):
        self.run_id = run_id
        self.budget_ceiling_usd = budget_ceiling_usd
        self.calls: List[CallRecord] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cached_tokens = 0
        self.total_tokens = 0
        self.cumulative_cost_usd = 0.0
        self.stage_breakdown: Dict[str, Dict[str, float]] = {}

    def record_call(
        self,
        call_id: str,
        stage: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
        latency_seconds: float
    ) -> CallRecord:
        """Record an API call, update running totals, and check ceilings."""
        cost = calculate_cost(model, prompt_tokens, completion_tokens, cached_tokens)
        total = prompt_tokens + completion_tokens
        
        record = CallRecord(
            call_id=call_id,
            run_id=self.run_id,
            stage=stage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total,
            cost_usd=cost,
            latency_seconds=round(latency_seconds, 3)
        )
        
        self.calls.append(record)
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cached_tokens += cached_tokens
        self.total_tokens += total
        self.cumulative_cost_usd = round(self.cumulative_cost_usd + cost, 6)
        
        if stage not in self.stage_breakdown:
            self.stage_breakdown[stage] = {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0
            }
        
        stage_entry = self.stage_breakdown[stage]
        stage_entry["calls"] += 1
        stage_entry["prompt_tokens"] += prompt_tokens
        stage_entry["completion_tokens"] += completion_tokens
        stage_entry["total_tokens"] += total
        stage_entry["cost_usd"] = round(stage_entry["cost_usd"] + cost, 6)
        
        logger.info(
            f"[USAGE] Run {self.run_id} | Stage: {stage} | Model: {model} | "
            f"Tokens: {total} (P:{prompt_tokens}/C:{completion_tokens}) | "
            f"Cost: ${cost:.5f} | Cumulative: ${self.cumulative_cost_usd:.4f} / ${self.budget_ceiling_usd:.2f}"
        )
        
        return record

    def is_budget_exceeded(self) -> bool:
        """Check if cumulative run spend has crossed the hard budget ceiling."""
        return self.cumulative_cost_usd >= self.budget_ceiling_usd

    def summary(self) -> Dict[str, any]:
        """Return a structured summary of the run's token and cost expenditure."""
        return {
            "run_id": self.run_id,
            "total_calls": len(self.calls),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "cached_tokens": self.total_cached_tokens,
            "total_cost_usd": round(self.cumulative_cost_usd, 4),
            "budget_ceiling_usd": self.budget_ceiling_usd,
            "budget_exhausted": self.is_budget_exceeded(),
            "stage_breakdown": self.stage_breakdown
        }

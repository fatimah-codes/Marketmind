"""
MarketMind AI - LLM Client Abstraction
Robust, resilient client wrapper over official OpenAI SDK.
Implements bounded retries with jitter, differentiated error handling,
request timeouts, structured logging, and token cost attribution.
"""

import time
import random
import uuid
import logging
from typing import List, Dict, Any, Optional, Union
import openai
from openai import OpenAI, RateLimitError, APIConnectionError, InternalServerError, AuthenticationError, BadRequestError

from src.config import Settings, StageConfig
from src.llm.usage import RunUsageTracker, CallRecord

logger = logging.getLogger("marketmind.llm")


class LLMClientError(Exception):
    """Base exception for LLM client failures."""
    pass


class AuthenticationFailure(LLMClientError):
    """Raised when API key is invalid or unauthorized."""
    pass


class RateLimitExceeded(LLMClientError):
    """Raised when rate limits are exhausted after all retries."""
    pass


class ContextLengthExceeded(LLMClientError):
    """Raised when input context exceeds model maximum."""
    pass


class BudgetCeilingExceeded(LLMClientError):
    """Raised when run budget ceiling is reached."""
    pass


class ModelRefusalOrEmpty(LLMClientError):
    """Raised when model returns empty or refused output."""
    pass


class LLMClient:
    """
    Unified LLM Client providing resilience, audit logging,
    and single-point cost attribution for all agent stages.
    """

    def __init__(self, settings: Settings, usage_tracker: Optional[RunUsageTracker] = None):
        self.settings = settings
        self.usage_tracker = usage_tracker or RunUsageTracker(run_id="default-run")
        self._sdk_client: Optional[OpenAI] = None

        if not self.settings.mock_mode:
            self._sdk_client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=self.settings.retry.timeout_seconds,
            )

    def set_usage_tracker(self, tracker: RunUsageTracker):
        """Set or update the active run usage tracker."""
        self.usage_tracker = tracker

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        stage: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature_override: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a chat completion with retries, backoff, and usage tracking.
        Returns a standardized dictionary with content, tool_calls, and call metadata.
        """
        # Budget check before making call
        if self.usage_tracker.is_budget_exceeded():
            raise BudgetCeilingExceeded(
                f"Run budget ceiling of ${self.usage_tracker.budget_ceiling_usd:.2f} exceeded. "
                f"Current spend: ${self.usage_tracker.cumulative_cost_usd:.4f}"
            )

        stage_cfg: StageConfig = self.settings.stages.get(
            stage,
            StageConfig(model="gpt-4o-mini", temperature=0.0)
        )
        model = stage_cfg.model
        temp = stage_cfg.temperature if temperature_override is None else temperature_override

        call_id = f"call-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # Handle Mock Mode for offline deterministic testing and evaluation
        if self.settings.mock_mode:
            return self._mock_completion(
                call_id=call_id,
                stage=stage,
                model=model,
                messages=messages,
                tools=tools,
                response_format=response_format,
                start_time=start_time
            )

        # Real OpenAI API Execution with retries
        retries = 0
        max_retries = self.settings.retry.max_retries
        backoff = self.settings.retry.initial_backoff_seconds

        while True:
            try:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temp,
                }
                if tools:
                    kwargs["tools"] = tools
                if tool_choice:
                    kwargs["tool_choice"] = tool_choice
                if response_format:
                    kwargs["response_format"] = response_format
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

                response = self._sdk_client.chat.completions.create(**kwargs)
                latency = time.time() - start_time

                # Extract token usage
                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                cached_tokens = 0
                if usage and hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
                    cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

                call_record = self.usage_tracker.record_call(
                    call_id=call_id,
                    stage=stage,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cached_tokens=cached_tokens,
                    latency_seconds=latency
                )

                choice = response.choices[0]
                message = choice.message

                # Check for refusal or empty
                if getattr(message, "refusal", None):
                    logger.warning(f"[{stage}] Model returned refusal: {message.refusal}")
                    raise ModelRefusalOrEmpty(f"Model refusal: {message.refusal}")

                # Format tool calls if present
                tool_calls_data = None
                if message.tool_calls:
                    tool_calls_data = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in message.tool_calls
                    ]

                return {
                    "call_id": call_id,
                    "content": message.content or "",
                    "tool_calls": tool_calls_data,
                    "finish_reason": choice.finish_reason,
                    "model": response.model,
                    "usage": call_record,
                }

            except AuthenticationError as e:
                logger.error(f"[AUTH ERROR] OpenAI authentication failed for stage '{stage}': {str(e)}")
                raise AuthenticationFailure(f"OpenAI Authentication Error: {str(e)}") from e

            except BadRequestError as e:
                err_msg = str(e).lower()
                if "context_length_exceeded" in err_msg or "maximum context length" in err_msg:
                    logger.error(f"[CONTEXT EXCEEDED] Context window exceeded in stage '{stage}': {str(e)}")
                    raise ContextLengthExceeded(f"Context length limit reached: {str(e)}") from e
                logger.error(f"[BAD REQUEST] Invalid request parameters in stage '{stage}': {str(e)}")
                raise LLMClientError(f"Bad Request: {str(e)}") from e

            except (RateLimitError, APIConnectionError, InternalServerError) as e:
                retries += 1
                if retries > max_retries:
                    logger.error(f"[EXHAUSTED] Retries exhausted ({max_retries}) for stage '{stage}': {str(e)}")
                    if isinstance(e, RateLimitError):
                        raise RateLimitExceeded(f"Rate limit exceeded after {max_retries} retries: {str(e)}") from e
                    raise LLMClientError(f"Transient failure exhausted retries: {str(e)}") from e

                # Add jitter: +/- 20%
                jitter = random.uniform(0.0, 0.5)
                sleep_time = min(backoff + jitter, self.settings.retry.max_backoff_seconds)
                logger.warning(
                    f"[RETRY {retries}/{max_retries}] Transient error '{type(e).__name__}' in stage '{stage}'. "
                    f"Backing off for {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
                backoff *= 2.0

            except Exception as e:
                logger.error(f"[UNEXPECTED FAILURE] LLM call failed in stage '{stage}': {str(e)}", exc_info=True)
                raise LLMClientError(f"Unexpected API call error: {str(e)}") from e

    def _mock_completion(
        self,
        call_id: str,
        stage: str,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        response_format: Optional[Dict[str, Any]],
        start_time: float
    ) -> Dict[str, Any]:
        """
        Deterministic mock generator for local testing and CI without API keys.
        Returns structurally valid schema responses tailored to the stage.
        """
        import json
        latency = time.time() - start_time
        prompt_tokens = sum(len(m.get("content", "")) // 4 for m in messages) + 100
        completion_tokens = 150
        
        call_record = self.usage_tracker.record_call(
            call_id=call_id,
            stage=stage,
            model="mock-model",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=0,
            latency_seconds=latency
        )

        content = ""
        tool_calls = None

        if stage == "request_analyser":
            content = json.dumps({
                "entity_type": "AI-powered customer support software",
                "segment": "Mid-market and Enterprise B2B SaaS",
                "geography": "Global (North America & EMEA focus)",
                "time_horizon": "Current (2025-2026)",
                "deliverable_type": "Market Intelligence Brief",
                "ambiguity_list": [
                    "Client request did not specify geographical focus.",
                    "Client did not define whether internal IT helpdesk or customer-facing support is primary."
                ],
                "assumptions": [
                    "Assuming external customer-facing support platforms are primary scope.",
                    "Assuming global enterprise & mid-market vendor focus."
                ]
            })

        elif stage == "planner":
            content = json.dumps({
                "plan_id": f"plan-{uuid.uuid4().hex[:6]}",
                "target_entity_type": "AI Customer Support Platforms",
                "objectives": [
                    {
                        "objective_id": "OBJ-1",
                        "title": "Vendor Identification & Market Landscape",
                        "description": "Identify market leaders, emerging entrants, and core architectural approaches.",
                        "sub_questions": [
                            {
                                "question_id": "Q-101",
                                "question_text": "Which vendors lead the AI-powered customer support category?",
                                "required_evidence_type": "analyst_note",
                                "candidate_tools": ["search_information", "retrieve_document"],
                                "priority": "critical",
                                "status": "open"
                            },
                            {
                                "question_id": "Q-102",
                                "question_text": "What are the primary architectural approaches (autonomous agents vs copilot copilots)?",
                                "required_evidence_type": "vendor_doc",
                                "candidate_tools": ["search_information", "retrieve_document"],
                                "priority": "high",
                                "status": "open"
                            }
                        ]
                    },
                    {
                        "objective_id": "OBJ-2",
                        "title": "Commercial Models and Pricing Structure",
                        "description": "Establish published per-seat, resolution-based, and enterprise licensing models.",
                        "sub_questions": [
                            {
                                "question_id": "Q-201",
                                "question_text": "Which vendors publish per-seat entry pricing, and what are the specific tiers?",
                                "required_evidence_type": "pricing_table",
                                "candidate_tools": ["search_information", "retrieve_document"],
                                "priority": "critical",
                                "status": "open"
                            },
                            {
                                "question_id": "Q-202",
                                "question_text": "How do consumption or per-resolution pricing models compare across vendors?",
                                "required_evidence_type": "pricing_table",
                                "candidate_tools": ["search_information", "retrieve_document", "calculate_metric"],
                                "priority": "high",
                                "status": "open"
                            }
                        ]
                    },
                    {
                        "objective_id": "OBJ-3",
                        "title": "Feature Differentiation & Limitations",
                        "description": "Evaluate automated resolution metrics, channel integrations, and verified gaps.",
                        "sub_questions": [
                            {
                                "question_id": "Q-301",
                                "question_text": "What verified resolution rates and SLA commitments are published by leading vendors?",
                                "required_evidence_type": "independent_benchmark",
                                "candidate_tools": ["search_information", "retrieve_document", "compare_companies"],
                                "priority": "high",
                                "status": "open"
                            },
                            {
                                "question_id": "Q-302",
                                "question_text": "What enterprise custom fine-tuning or SLA tiers remain unestablished or undisclosed?",
                                "required_evidence_type": "vendor_doc",
                                "candidate_tools": ["search_information", "retrieve_document"],
                                "priority": "medium",
                                "status": "open"
                            }
                        ]
                    }
                ],
                "candidate_tools": ["search_information", "retrieve_document", "calculate_metric", "compare_companies", "save_research"]
            })

        elif stage == "researcher":
            # Deterministic mock sequence executing actual tools against local corpus
            # Check how many calls have been made in researcher stage so far
            res_calls = self.usage_tracker.stage_breakdown.get("researcher", {}).get("calls", 0)
            if res_calls <= 1:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "search_information",
                        "arguments": json.dumps({
                            "query": "Zendesk Intercom pricing and resolution rates",
                            "source_type": "all",
                            "max_results": 5,
                            "recency_window": "any"
                        })
                    }
                }]
            elif res_calls == 2:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "retrieve_document",
                        "arguments": json.dumps({
                            "document_id": "DOC-ZD-02",
                            "section": None
                        })
                    }
                }]
            elif res_calls == 3:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "retrieve_document",
                        "arguments": json.dumps({
                            "document_id": "DOC-INT-02",
                            "section": None
                        })
                    }
                }]
            elif res_calls == 4:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "retrieve_document",
                        "arguments": json.dumps({
                            "document_id": "DOC-ANA-03",
                            "section": None
                        })
                    }
                }]
            elif res_calls == 5:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "calculate_metric",
                        "arguments": json.dumps({
                            "operation": "cagr",
                            "values": [4.8, 9.6],
                            "period": 3.0
                        })
                    }
                }]
            elif res_calls == 6:
                tool_calls = [{
                    "id": f"tc-{uuid.uuid4().hex[:6]}",
                    "type": "function",
                    "function": {
                        "name": "retrieve_document",
                        "arguments": json.dumps({
                            "document_id": "DOC-GOR-02",
                            "section": None
                        })
                    }
                }]
            else:
                content = "All identified open sub-questions have been thoroughly researched across verified sources."

        elif stage == "quality_control":
            content = json.dumps({
                "verdict": "PASS",
                "defects": [],
                "unsupported_claims_count": 0,
                "missing_sources_count": 0,
                "coverage_gaps_count": 0,
                "contradictions_count": 0,
                "low_confidence_count": 0,
                "targeted_gap_questions": []
            })

        else:
            content = "Mock response generated for stage: " + stage

        return {
            "call_id": call_id,
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": "stop",
            "model": "mock-model",
            "usage": call_record,
        }

"""
MarketMind AI - Research Planner Component
Task 03 and Task 04 requirement.
Decomposes normalized scope into an inspectable, bounded research plan.
Enforces answerability, validates invariants, and implements bounded retry with error feedback.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from src.llm.client import LLMClient
from src.schemas.plan import (
    ResearchPlan,
    ResearchObjective,
    SubQuestion,
    EvidenceType,
    QuestionPriority,
    QuestionStatus,
    CandidateTool,
    validate_plan_invariants
)
from src.state.research_state import ResearchState

logger = logging.getLogger("marketmind.agent.planner")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planner_v1.txt"


class ResearchPlanner:
    """Produces structured, validated research plans."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    def generate_plan(self, scope: Dict[str, Any], state: ResearchState) -> ResearchPlan:
        """
        Generate research plan conforming to Section 4.1 & 6.1 contract.
        Validates in code, retries on failure with error feedback, or uses typed fallback.
        """
        logger.info("[PLANNING] Generating structured research plan from scope...")

        user_prompt = (
            f"Scope Definition:\n{json.dumps(scope, indent=2)}\n\n"
            "Generate a structured research plan for this commission. "
            "Define 3 to 5 strategic objectives. For each objective, specify 2 to 4 answerable, "
            "bounded sub-questions. Assign required evidence type and candidate tools for each. "
            "Ensure questions investigate pricing models, market leaders, architectural trade-offs, and gaps."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # First Attempt
        plan_obj = self._call_and_parse(messages)
        validation_errors = validate_plan_invariants(plan_obj) if plan_obj else ["Failed to parse plan JSON"]

        # Retry once with error feedback if invalid (Task 03 failure path)
        if validation_errors:
            logger.warning(f"[PLAN RETRY] Plan failed invariant validation: {validation_errors}. Retrying with feedback...")
            retry_messages = list(messages)
            retry_messages.append({"role": "assistant", "content": json.dumps(plan_obj.model_dump() if plan_obj else {})})
            retry_messages.append({
                "role": "user",
                "content": (
                    f"The previous plan failed invariant validation with the following errors:\n"
                    + "\n".join(f"- {e}" for e in validation_errors)
                    + "\nPlease correct all issues and return a valid plan."
                )
            })

            plan_obj = self._call_and_parse(retry_messages)
            validation_errors = validate_plan_invariants(plan_obj) if plan_obj else ["Failed second parse"]

        # If still invalid, activate deterministic typed fallback
        if validation_errors or not plan_obj:
            logger.warning("[PLAN FALLBACK] Plan validation failed after retry. Using typed fallback plan.")
            plan_obj = self._generate_fallback_plan(scope)

        state.plan = plan_obj
        state.current_stage = "researcher"
        state.touch()

        total_questions = sum(len(o.sub_questions) for o in plan_obj.objectives)
        logger.info(
            f"[PLAN READY] Plan ID: {plan_obj.plan_id} | Objectives: {len(plan_obj.objectives)} | "
            f"Total Sub-Questions: {total_questions}"
        )

        return plan_obj

    def _call_and_parse(self, messages: List[Dict[str, Any]]) -> Optional[ResearchPlan]:
        """Invoke model and parse into ResearchPlan Pydantic model."""
        try:
            res = self.llm.chat_completion(
                messages=messages,
                stage="planner",
                response_format={"type": "json_object"}
            )
            data = json.loads(res.get("content", "{}"))
            return ResearchPlan.model_validate(data)
        except Exception as e:
            logger.error(f"Error parsing research plan: {e}")
            return None

    def _generate_fallback_plan(self, scope: Dict[str, Any]) -> ResearchPlan:
        """Deterministic typed fallback plan satisfying all validation invariants."""
        return ResearchPlan(
            plan_id="plan-standard-s1",
            target_entity_type=scope.get("entity_type", "AI Customer Support Software"),
            objectives=[
                ResearchObjective(
                    objective_id="OBJ-1",
                    title="Competitive Landscape and Vendor Architectures",
                    description="Identify established enterprise vendors, emerging challengers, and core AI architectures.",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-101",
                            question_text="Which vendors dominate the AI customer support market and what are their primary positioning strategies?",
                            required_evidence_type=EvidenceType.ANALYST_NOTE,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT],
                            priority=QuestionPriority.CRITICAL
                        ),
                        SubQuestion(
                            question_id="Q-102",
                            question_text="How do vendor architectures differentiate between autonomous resolution bots and human agent copilots?",
                            required_evidence_type=EvidenceType.VENDOR_DOC,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT],
                            priority=QuestionPriority.HIGH
                        )
                    ]
                ),
                ResearchObjective(
                    objective_id="OBJ-2",
                    title="Pricing Structures and Total Cost of Ownership",
                    description="Analyze per-seat, consumption, and resolution-based commercial pricing models.",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-201",
                            question_text="What are the published per-seat starting prices and tiers for Zendesk, Intercom, and Freshworks?",
                            required_evidence_type=EvidenceType.PRICING_TABLE,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT],
                            priority=QuestionPriority.CRITICAL
                        ),
                        SubQuestion(
                            question_id="Q-202",
                            question_text="How do consumption and resolution-based fees (e.g. Intercom Fin vs Salesforce Agentforce) compare?",
                            required_evidence_type=EvidenceType.PRICING_TABLE,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT, CandidateTool.CALCULATE_METRIC],
                            priority=QuestionPriority.HIGH
                        )
                    ]
                ),
                ResearchObjective(
                    objective_id="OBJ-3",
                    title="Empirical Performance, Benchmarks, and Operational Gaps",
                    description="Assess deflection rates, reported conflicts, and unestablished enterprise attributes.",
                    sub_questions=[
                        SubQuestion(
                            question_id="Q-301",
                            question_text="What empirical resolution and deflection rates are documented in independent benchmarks versus vendor claims?",
                            required_evidence_type=EvidenceType.INDEPENDENT_BENCHMARK,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT, CandidateTool.COMPARE_COMPANIES],
                            priority=QuestionPriority.HIGH
                        ),
                        SubQuestion(
                            question_id="Q-302",
                            question_text="What enterprise custom fine-tuning pricing and SLA uptime commitments remain unestablished in public documentation?",
                            required_evidence_type=EvidenceType.VENDOR_DOC,
                            candidate_tools=[CandidateTool.SEARCH_INFORMATION, CandidateTool.RETRIEVE_DOCUMENT],
                            priority=QuestionPriority.MEDIUM
                        )
                    ]
                )
            ]
        )

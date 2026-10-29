"""
MarketMind AI - Research Agent (The Bounded Agent Loop)
Task 06 requirement.
Self-implemented plan-act-observe loop with:
- Five independent termination conditions:
  1. All questions resolved
  2. Iteration cap reached
  3. Tool call cap reached
  4. Cumulative budget ceiling reached
  5. Stuck-loop detection (repetition hash)
- Per-question context scoping (avoids context explosion)
- Parallel tool call execution
- Clean partial result handling if bounds trip
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from src.llm.client import LLMClient
from src.tools.dispatcher import ToolDispatcher
from src.schemas.plan import ResearchPlan, SubQuestion, QuestionStatus
from src.schemas.evidence import EvidenceStore
from src.state.research_state import ResearchState
from src.agents.evidence_analyst import EvidenceAnalyst

logger = logging.getLogger("marketmind.agent.researcher")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "researcher_v1.txt"


class ResearchAgentLoop:
    """
    Executes the autonomous, bounded research loop over open sub-questions.
    No external agent framework used.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        dispatcher: ToolDispatcher,
        evidence_analyst: Optional[EvidenceAnalyst] = None
    ):
        self.llm = llm_client
        self.dispatcher = dispatcher
        self.evidence_analyst = evidence_analyst or EvidenceAnalyst()
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    def run_loop(self, state: ResearchState) -> ResearchState:
        """
        Execute the bounded research loop until termination conditions are reached.
        """
        logger.info(f"[AGENT LOOP START] Starting autonomous loop for run '{state.run_id}'...")
        state.current_stage = "researcher"

        # Bounds from configuration
        max_iterations = state.scope.get("max_iterations", 15)
        max_tool_calls = state.scope.get("max_tool_calls", 30)

        # Call history hashes for stuck-loop detection
        recent_call_hashes: List[str] = []

        while True:
            state.iteration_count += 1
            logger.info(f"[ITERATION {state.iteration_count}/{max_iterations}]")

            # ----------------------------------------------------
            # Check Termination Condition 1: Budget Ceiling
            # ----------------------------------------------------
            if self.llm.usage_tracker.is_budget_exceeded():
                logger.warning("[LOOP TERMINATION] Cumulative run budget ceiling exceeded! Halting cleanly.")
                state.is_incomplete = True
                state.termination_reason = f"Budget ceiling of ${self.llm.usage_tracker.budget_ceiling_usd:.2f} reached."
                break

            # ----------------------------------------------------
            # Check Termination Condition 2: Iteration Cap
            # ----------------------------------------------------
            if state.iteration_count > max_iterations:
                logger.warning(f"[LOOP TERMINATION] Iteration cap of {max_iterations} reached. Halting cleanly.")
                state.is_incomplete = True
                state.termination_reason = f"Iteration cap of {max_iterations} reached."
                break

            # ----------------------------------------------------
            # Check Termination Condition 3: Tool Call Cap
            # ----------------------------------------------------
            if state.tool_call_count >= max_tool_calls:
                logger.warning(f"[LOOP TERMINATION] Max tool call cap of {max_tool_calls} reached. Halting cleanly.")
                state.is_incomplete = True
                state.termination_reason = f"Tool call ceiling of {max_tool_calls} reached."
                break

            # ----------------------------------------------------
            # Check Termination Condition 4: All Questions Resolved
            # ----------------------------------------------------
            open_questions = state.get_open_questions()
            if not open_questions:
                logger.info("[LOOP TERMINATION] All planned sub-questions resolved successfully!")
                state.is_incomplete = False
                state.termination_reason = "All questions resolved."
                break

            # ----------------------------------------------------
            # Sub-Question Selection Policy: Highest Priority Open Question
            # ----------------------------------------------------
            current_q = self._select_next_question(open_questions)
            logger.info(f"[CURRENT SUB-QUESTION] {current_q.question_id}: {current_q.question_text}")

            # ----------------------------------------------------
            # Context Management Strategy: Per-Question Scoping
            # Assemble only the active sub-question, plan objective context,
            # and already-established evidence IDs (prevents monotonic transcript bloat)
            # ----------------------------------------------------
            messages = self._assemble_context_slice(current_q, state)

            # Get tool definitions
            tool_defs = self.dispatcher.registry.get_openai_tool_definitions()

            # Execute Model Call
            try:
                model_response = self.llm.chat_completion(
                    messages=messages,
                    stage="researcher",
                    tools=tool_defs,
                    tool_choice="auto"
                )
            except Exception as e:
                logger.error(f"[LLM ERROR IN LOOP] Failed model invocation: {e}")
                # Mark question unanswerable to prevent infinite error loops
                state.mark_question_status(
                    current_q.question_id,
                    QuestionStatus.UNANSWERABLE,
                    notes=f"API failure during research: {str(e)}"
                )
                continue

            tool_calls = model_response.get("tool_calls")

            # If model returned no tool calls, evaluate text or mark question
            if not tool_calls:
                text_content = model_response.get("content", "")
                logger.info(f"[MODEL TEXT RESPONSE] {text_content[:120]}...")
                # If question has evidence in store, mark answered; otherwise mark unanswerable
                existing_for_q = state.evidence_store.get_by_question(current_q.question_id)
                if existing_for_q:
                    state.mark_question_status(current_q.question_id, QuestionStatus.ANSWERED, "Answered via gathered evidence.")
                else:
                    state.mark_question_status(current_q.question_id, QuestionStatus.UNANSWERABLE, "Model produced no tool calls for ungrounded question.")
                continue

            # ----------------------------------------------------
            # Dispatch Tool Calls (Supporting Parallel Tool Calls)
            # ----------------------------------------------------
            for tc in tool_calls:
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")

                # Check Termination Condition 5: Stuck Loop Detection
                call_hash = self._compute_call_hash(t_name, raw_args)
                if recent_call_hashes.count(call_hash) >= 2:
                    logger.warning(
                        f"[STUCK LOOP DETECTED] Repeated call to '{t_name}' with identical arguments! "
                        f"Breaking repetition and forcing question advancement."
                    )
                    state.mark_question_status(
                        current_q.question_id,
                        QuestionStatus.UNANSWERABLE,
                        notes="Marked unanswerable due to stuck loop repetition."
                    )
                    break

                recent_call_hashes.append(call_hash)
                if len(recent_call_hashes) > 6:
                    recent_call_hashes.pop(0)

                # Dispatch via dispatcher pipeline
                context_dict = {"state": state, "corpus_dir": state.scope.get("corpus_dir")}
                result = self.dispatcher.dispatch(
                    tool_name=t_name,
                    raw_arguments=raw_args,
                    stage="researcher",
                    context=context_dict
                )

                # Process result through Evidence Analyst if search or retrieve
                self._process_tool_result_for_evidence(
                    tool_name=t_name,
                    tool_result=result,
                    current_q=current_q,
                    state=state
                )

            # Check if this sub-question now has sufficient evidence
            evidence_for_q = state.evidence_store.get_by_question(current_q.question_id)
            if evidence_for_q:
                state.mark_question_status(
                    current_q.question_id,
                    QuestionStatus.ANSWERED,
                    notes=f"Answered with {len(evidence_for_q)} verified evidence records."
                )

        state.touch()
        logger.info(
            f"[AGENT LOOP FINISHED] Status: {'INCOMPLETE' if state.is_incomplete else 'COMPLETE'} | "
            f"Iterations: {state.iteration_count} | Tool Calls: {state.tool_call_count} | "
            f"Evidence Stored: {len(state.evidence_store.records)}"
        )
        return state

    def _select_next_question(self, open_questions: List[SubQuestion]) -> SubQuestion:
        """
        Selection Policy: Priority-ranked FIFO.
        Critical -> High -> Medium -> Low.
        """
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_qs = sorted(open_questions, key=lambda q: priority_rank.get(q.priority.value, 99))
        return sorted_qs[0]

    def _assemble_context_slice(self, current_q: SubQuestion, state: ResearchState) -> List[Dict[str, str]]:
        """
        Deliberate Context Management:
        Per-question context slice containing system prompt, targeted question prompt,
        and compact summary of existing evidence keys. Prevents linear context growth.
        """
        existing_evidence_summary = [
            f"[{e.evidence_id}] ({e.claim_type.value}) {e.claim[:100]}... (Source: {e.source_ref})"
            for e in state.evidence_store.records[-6:]
        ]
        evidence_text = "\n".join(existing_evidence_summary) if existing_evidence_summary else "No evidence collected yet."

        user_content = (
            f"TARGET RESEARCH SUB-QUESTION:\n"
            f"Question ID: {current_q.question_id}\n"
            f"Question: \"{current_q.question_text}\"\n"
            f"Required Evidence Type: {current_q.required_evidence_type.value}\n"
            f"Candidate Tools: {[t.value for t in current_q.candidate_tools]}\n\n"
            f"RECENT VALIDATED EVIDENCE IN STORE:\n{evidence_text}\n\n"
            "Instructions:\n"
            "Call the appropriate tool to research this specific question. "
            "If searching for facts, use `search_information` or `retrieve_document`. "
            "If performing arithmetic on figures, use `calculate_metric`. "
            "When factual data is retrieved, save each distinct finding using `save_research`. "
            "Do NOT invent figures or hallucinate citations."
        )

        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content}
        ]

    def _compute_call_hash(self, tool_name: str, arguments: Any) -> str:
        """Generate normalized hash of tool name and arguments for stuck-loop detection."""
        norm_args = ""
        if isinstance(arguments, dict):
            norm_args = json.dumps(arguments, sort_keys=True)
        elif isinstance(arguments, str):
            try:
                norm_args = json.dumps(json.loads(arguments), sort_keys=True)
            except Exception:
                norm_args = arguments.strip()
        h = hashlib.sha256(f"{tool_name}:{norm_args}".encode("utf-8")).hexdigest()
        return h

    def _process_tool_result_for_evidence(
        self,
        tool_name: str,
        tool_result: Dict[str, Any],
        current_q: SubQuestion,
        state: ResearchState
    ):
        """Pass raw tool results into Evidence Analyst to validate candidate claims."""
        if not isinstance(tool_result, dict) or tool_result.get("status") == "error":
            return

        if tool_name == "retrieve_document":
            doc_id = tool_result.get("document_id", "")
            full_text = tool_result.get("full_text", "")
            source_type = tool_result.get("source_type", "vendor_doc")

            # Extract paragraphs / bullet claims and evaluate
            paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 30]
            for p in paragraphs[:3]:  # Top 3 key paragraphs
                self.evidence_analyst.evaluate_candidate_claim(
                    question_id=current_q.question_id,
                    question_text=current_q.question_text,
                    claim=p[:300],
                    source_id=doc_id,
                    source_type=source_type,
                    source_text=full_text,
                    state=state
                )

        elif tool_name == "search_information":
            hits = tool_result.get("hits", [])
            for hit in hits[:3]:
                snippet = hit.get("snippet", "")
                doc_id = hit.get("document_id", hit.get("hit_id", ""))
                stype = hit.get("source_type", "search_hit")
                self.evidence_analyst.evaluate_candidate_claim(
                    question_id=current_q.question_id,
                    question_text=current_q.question_text,
                    claim=snippet,
                    source_id=doc_id,
                    source_type=stype,
                    source_text=snippet,
                    state=state
                )

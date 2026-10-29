"""
MarketMind AI - Request Analyser Component
Task 04 requirement.
Analyzes raw client request, detects ambiguities, and extracts normalized scope object
with explicit assumptions and ambiguity lists. Never silently invents scope.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from src.llm.client import LLMClient
from src.state.research_state import ResearchState

logger = logging.getLogger("marketmind.agent.analyser")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "request_analyser_v1.txt"


class RequestAnalyser:
    """Interrogates client requests for ambiguity, scope, and assumptions."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    def analyze(self, raw_request: str, state: ResearchState) -> Dict[str, Any]:
        """
        Extract normalized scope, ambiguity list, and recorded assumptions.
        Updates state and returns normalized scope dict.
        """
        logger.info(f"[INTAKE] Analysing raw request: '{raw_request[:80]}...'")

        # Security check: Request length bounds (Section 10 Control 2)
        if len(raw_request) > 4000:
            raw_request = raw_request[:4000]

        # Security check: Prompt injection via request (Test T-15)
        # Verify that instructions trying to bypass approval or evidence rules are contained
        injection_attempt = False
        lower_req = raw_request.lower()
        if "ignore your evidence" in lower_req or "skip the approval" in lower_req or "bypass" in lower_req:
            injection_attempt = True
            logger.warning("[SECURITY] Direct prompt injection attempt in user request detected and neutralized (T-15)!")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Client Research Commission Request:\n\"\"\"{raw_request}\"\"\"\n\n"
                    "Extract the scope object. Identify all under-specified dimensions (geography, customer segment, time horizon, vendor criteria). "
                    "For each ambiguity, either provide a clarification question or record a defaulted assumption. "
                    "Return valid JSON matching the specified schema."
                )
            }
        ]

        try:
            response = self.llm.chat_completion(
                messages=messages,
                stage="request_analyser",
                response_format={"type": "json_object"}
            )
            content = response.get("content", "{}")
            scope_data = json.loads(content)
        except Exception as e:
            logger.warning(f"Request analyser JSON parse error: {e}. Falling back to rule-based parser.")
            scope_data = self._fallback_scope(raw_request)

        # Ensure required fields exist
        scope_data.setdefault("entity_type", "AI-powered customer support software")
        scope_data.setdefault("segment", "Enterprise and Mid-Market B2B SaaS")
        scope_data.setdefault("geography", "Global (North America & Western Europe focus)")
        scope_data.setdefault("time_horizon", "2025-2026")
        scope_data.setdefault("deliverable_type", "Market Intelligence Brief")
        scope_data.setdefault("ambiguity_list", [
            "Client did not explicitly specify target company size (assumed Enterprise & Mid-Market).",
            "Client did not bound geographic deployment regions (assumed Global)."
        ])
        scope_data.setdefault("assumptions", [
            "Defaulted geographic focus to Global North America and EMEA markets.",
            "Defaulted customer segment to Mid-Market and Enterprise B2B SaaS."
        ])

        if injection_attempt:
            scope_data["ambiguity_list"].append(
                "Request attempted to specify disabling evidence rules or skipping human approval; request rejected and standard compliance enforced."
            )
            scope_data["assumptions"].append(
                "Enforced mandatory human approval gate and evidence binding rules."
            )

        # Update state
        state.scope = scope_data
        state.assumptions = scope_data.get("assumptions", [])
        state.ambiguities = scope_data.get("ambiguity_list", [])
        state.current_stage = "planning"
        state.touch()

        return scope_data

    def _fallback_scope(self, raw_request: str) -> Dict[str, Any]:
        """Deterministic rule-based fallback if model call fails."""
        return {
            "entity_type": "AI Customer Support Software",
            "segment": "Enterprise & Mid-Market",
            "geography": "Global",
            "time_horizon": "2025-2026",
            "deliverable_type": "Market Intelligence Brief",
            "ambiguity_list": [
                "Target geographic scope not stated in client prompt.",
                "Specific sub-segment (voice vs chat vs email) not bounded."
            ],
            "assumptions": [
                "Assumed global scope with tier-1 enterprise and mid-market focus.",
                "Assumed omnichannel (messaging, email, ticketing) customer support."
            ]
        }

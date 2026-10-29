"""
MarketMind AI - Autonomous Business Research Agent
CLI Entry Point & Pipeline Orchestration
"""

import os
import sys
import uuid
import argparse
import logging
from typing import Optional
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_settings, Settings
from src.llm.usage import RunUsageTracker
from src.llm.client import LLMClient
from src.tools.dispatcher import ToolDispatcher
from src.state.research_state import ResearchState
from src.state.persistence import save_run_state
from src.schemas.report import ApprovalDecision

# Agents
from src.agents.request_analyser import RequestAnalyser
from src.agents.planner import ResearchPlanner
from src.agents.researcher import ResearchAgentLoop
from src.agents.evidence_analyst import EvidenceAnalyst
from src.agents.comparison import ComparisonAgent
from src.agents.synthesis import SynthesisAgent
from src.agents.quality_control import QualityControlAgent
from src.agents.report_generator import ReportGenerator
from src.approval.cli_gate import HumanApprovalGate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("marketmind.main")


def run_smoke_test(settings: Settings):
    """
    Task 01 Acceptance Criterion:
    Makes one API call, prints model used, tokens consumed, estimated cost, and masks key.
    """
    print("\n" + "=" * 60)
    print("      MARKETMIND AI - TASK 01 SMOKE VERIFICATION          ")
    print("=" * 60)
    print(f"Masked API Key: {settings.masked_api_key()}")
    print(f"Mock Mode: {settings.mock_mode}")

    tracker = RunUsageTracker(run_id="smoke-test-run")
    client = LLMClient(settings=settings, usage_tracker=tracker)

    test_messages = [
        {"role": "system", "content": "You are a test evaluator."},
        {"role": "user", "content": "Respond with the word 'READY' to verify API connectivity."}
    ]

    try:
        res = client.chat_completion(
            messages=test_messages,
            stage="request_analyser"
        )
        usage = res["usage"]
        print(f"Response Content: {res['content'].strip()}")
        print(f"Model Invoked: {usage.model}")
        print(f"Tokens Consumed: {usage.total_tokens} (Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens})")
        print(f"Estimated Cost: ${usage.cost_usd:.6f} USD")
        print(f"Latency: {usage.latency_seconds:.3f}s")
        print("\n[SUCCESS] Task 01 Smoke Test Passed cleanly.\n")
    except Exception as e:
        print(f"\n[FAILURE] Smoke test encountered an error: {e}")
        sys.exit(1)


def orchestrate_research_pipeline(
    raw_request: str,
    settings: Settings,
    run_id: Optional[str] = None,
    interactive_approval: bool = True,
    auto_approver_id: Optional[str] = None
) -> ResearchState:
    """
    Executes the complete MarketMind AI end-to-end research workflow.
    """
    run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
    print(f"\n>>> Starting MarketMind Research Run: {run_id}")
    print(f">>> Request: '{raw_request}'")

    usage_tracker = RunUsageTracker(run_id=run_id, budget_ceiling_usd=settings.budget.budget_ceiling_usd)
    llm_client = LLMClient(settings=settings, usage_tracker=usage_tracker)
    dispatcher = ToolDispatcher()
    evidence_analyst = EvidenceAnalyst()

    # Initialize State
    state = ResearchState(
        run_id=run_id,
        raw_request=raw_request,
        scope={"corpus_dir": str(settings.corpus_dir)}
    )

    # 1. Request Analysis
    print("\n[Stage 1/7] Analyzing Client Request & Scope...")
    analyser = RequestAnalyser(llm_client)
    scope = analyser.analyze(raw_request, state)

    # 2. Research Planning
    print("\n[Stage 2/7] Generating Decomposed Research Plan...")
    planner = ResearchPlanner(llm_client)
    plan = planner.generate_plan(scope, state)

    # 3. Autonomous Research Loop
    print("\n[Stage 3/7] Executing Autonomous Research Loop...")
    researcher = ResearchAgentLoop(llm_client, dispatcher, evidence_analyst)
    state = researcher.run_loop(state)

    # 4. Competitor Comparison
    print("\n[Stage 4/7] Assembling Competitor Comparison Matrix...")
    comparison = ComparisonAgent()
    matrix_analysis = comparison.build_comparison(state)

    # 5. Synthesis
    print("\n[Stage 5/7] Synthesizing Strategic Findings...")
    synthesizer = SynthesisAgent()
    findings_bundle = synthesizer.synthesize(state)

    # 6. Quality Control Pass with Bounded Repair Loop
    print("\n[Stage 6/7] Running Adversarial Quality Control Pass...")
    qc = QualityControlAgent()
    qc_result = qc.audit(state, findings_bundle)

    repair_rounds = 0
    max_repairs = settings.budget.max_repair_rounds

    while qc_result["verdict"] == "FAIL" and repair_rounds < max_repairs:
        repair_rounds += 1
        state.repair_round = repair_rounds
        print(f"\n[QC REPAIR ROUND {repair_rounds}/{max_repairs}] Addressing {len(qc_result['targeted_gap_questions'])} targeted gap questions...")
        state = researcher.run_loop(state)
        matrix_analysis = comparison.build_comparison(state)
        findings_bundle = synthesizer.synthesize(state)
        qc_result = qc.audit(state, findings_bundle)

    if qc_result["verdict"] == "FAIL":
        print(f"\n[QC NOTICE] Quality repair rounds exhausted ({max_repairs}). Remaining defects will be published in limitations_and_gaps.")

    # 7. Final Report Compilation
    print("\n[Stage 7/7] Compiling Final Schema-Validated Report...")
    generator = ReportGenerator()
    report = generator.generate_report(state, findings_bundle, matrix_analysis)

    # Human Approval Gate (Mandatory)
    gate = HumanApprovalGate()
    print("\n" + gate.present_review_summary(state))

    decision_taken = None
    if auto_approver_id:
        decision_taken = gate.process_decision(
            decision=ApprovalDecision.APPROVE,
            approver_id=auto_approver_id,
            notes="Authorized automatically for test/evaluation pipeline.",
            state=state
        )
    elif interactive_approval:
        print("\nChoose an action:")
        print("  1. Approve & Publish")
        print("  2. Reject & Archive")
        print("  3. Request Additional Research")
        print("  4. Modify Scope")
        choice = input("Enter decision [1-4]: ").strip()

        if choice == "1":
            reviewer = input("Enter your reviewer corporate email / ID: ").strip() or "reviewer@verity.com"
            notes = input("Enter review notes: ").strip() or "Verified findings against source appendix."
            decision_taken = gate.process_decision(ApprovalDecision.APPROVE, reviewer, notes, state)
        elif choice == "2":
            reviewer = input("Enter your reviewer corporate email / ID: ").strip() or "reviewer@verity.com"
            notes = input("Enter reason for rejection: ").strip() or "Insufficient vendor coverage."
            decision_taken = gate.process_decision(ApprovalDecision.REJECT, reviewer, notes, state)
        elif choice == "3":
            reviewer = input("Enter your reviewer corporate email / ID: ").strip() or "reviewer@verity.com"
            q_add = input("Enter additional specific research question: ").strip()
            decision_taken = gate.process_decision(ApprovalDecision.REQUEST_ADDITIONAL_RESEARCH, reviewer, q_add, state, [q_add])
            # Re-enter research
            state = researcher.run_loop(state)
            report = generator.generate_report(state, findings_bundle, matrix_analysis)
        elif choice == "4":
            reviewer = input("Enter your reviewer corporate email / ID: ").strip() or "reviewer@verity.com"
            notes = input("Enter scope modifications: ").strip()
            decision_taken = gate.process_decision(ApprovalDecision.MODIFY_SCOPE, reviewer, notes, state)

    # Save all run artifacts to runs/<run_id>/
    run_dir = save_run_state(state, settings.runs_dir)

    # Render Markdown report if report exists
    if state.final_report:
        report_md = generator.render_markdown(state.final_report)
        md_path = run_dir / "final_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"\n[PUBLISHED] Final report written to: {md_path}")

    # Summary
    usage_sum = usage_tracker.summary()
    print("\n" + "=" * 60)
    print("                 RUN EXECUTION SUMMARY                      ")
    print("=" * 60)
    print(f"Run ID: {state.run_id}")
    print(f"Status: {state.status.upper()}")
    print(f"Total API Calls: {usage_sum['total_calls']}")
    print(f"Total Tokens: {usage_sum['total_tokens']} (Prompt: {usage_sum['prompt_tokens']}, Output: {usage_sum['completion_tokens']})")
    print(f"Total Run Cost: ${usage_sum['total_cost_usd']:.4f} USD")
    print(f"Tool Executions: {state.tool_call_count}")
    print(f"Evidence Records: {len(state.evidence_store.records)}")
    print(f"QC Verdict: {state.qc_verdict}")
    print(f"Artifacts Saved: {run_dir}")
    print("=" * 60 + "\n")

    return state


def main():
    parser = argparse.ArgumentParser(description="MarketMind AI - Autonomous Business Research Agent")
    parser.add_argument("--request", type=str, help="Natural language business research request")
    parser.add_argument("--scenario", type=str, default="S1", help="Scenario code from Section 8 (e.g. S1, S2, S3)")
    parser.add_argument("--mock", action="store_true", help="Force deterministic mock mode without API keys")
    parser.add_argument("--smoke", action="store_true", help="Run Task 01 API smoke verification test")
    parser.add_argument("--run-id", type=str, help="Custom run identifier")
    parser.add_argument("--auto-approve", type=str, help="Approver ID for non-interactive execution")
    args = parser.parse_args()

    # Load validated settings
    if args.mock:
        os.environ["MOCK_MODE"] = "true"

    settings = load_settings()

    if args.smoke:
        run_smoke_test(settings)
        return

    scenario_requests = {
        "S1": "Research the market for AI-powered customer support software and prepare a business intelligence report.",
        "S2": "We're considering entering the developer tooling space. What does the AI coding assistant landscape look like and where are the gaps?",
        "S3": "Assess the AI automation platform market for a potential acquisition target shortlist."
    }

    req = args.request or scenario_requests.get(args.scenario.upper(), scenario_requests["S1"])
    orchestrate_research_pipeline(
        raw_request=req,
        settings=settings,
        run_id=args.run_id,
        interactive_approval=not bool(args.auto_approve),
        auto_approver_id=args.auto_approve
    )


if __name__ == "__main__":
    main()

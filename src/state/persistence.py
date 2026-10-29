"""
MarketMind AI - State Persistence and Run Artifact Generator
Serializes and reloads state to disk under runs/<run_id>/.
Produces inspectable audit artifacts for viva and compliance.
"""

import json
from pathlib import Path
from typing import Optional
from src.state.research_state import ResearchState


def get_run_dir(run_id: str, base_runs_dir: Optional[Path] = None) -> Path:
    """Ensure and return the dedicated directory for this run."""
    if base_runs_dir is None:
        base_runs_dir = Path(__file__).resolve().parent.parent.parent / "runs"
    run_dir = base_runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_run_state(state: ResearchState, base_runs_dir: Optional[Path] = None) -> Path:
    """
    Save the complete research state and separate inspectable artifacts:
    1. state.json - full monolithic serializable state
    2. plan.json - the generated research plan
    3. tool_log.json - complete chronological list of tool calls & results
    4. evidence_store.json - validated evidence records & rejection log
    5. qc_verdict.json - quality control findings & defect list
    6. report.json / report.md - final report (if generated)
    """
    run_dir = get_run_dir(state.run_id, base_runs_dir)

    # 1. Full state.json
    state_file = run_dir / "state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))

    # 2. Plan artifact
    if state.plan:
        with open(run_dir / "plan.json", "w", encoding="utf-8") as f:
            f.write(state.plan.model_dump_json(indent=2))

    # 3. Tool log artifact
    with open(run_dir / "tool_log.json", "w", encoding="utf-8") as f:
        tool_records = [t.model_dump() for t in state.tool_history]
        json.dump(tool_records, f, indent=2)

    # 4. Evidence Store artifact
    with open(run_dir / "evidence_store.json", "w", encoding="utf-8") as f:
        f.write(state.evidence_store.model_dump_json(indent=2))

    # 5. QC Verdict artifact
    if state.qc_verdict:
        qc_data = {
            "verdict": state.qc_verdict,
            "defects": state.defect_list,
            "targeted_gap_questions": state.qc_targeted_gap_questions,
            "repair_round": state.repair_round
        }
        with open(run_dir / "qc_verdict.json", "w", encoding="utf-8") as f:
            json.dump(qc_data, f, indent=2)

    # 6. Final report artifact
    if state.final_report:
        with open(run_dir / "report.json", "w", encoding="utf-8") as f:
            f.write(state.final_report.model_dump_json(indent=2))

    return run_dir


def load_run_state(run_id: str, base_runs_dir: Optional[Path] = None) -> ResearchState:
    """Load a previously serialized research state from disk."""
    run_dir = get_run_dir(run_id, base_runs_dir)
    state_file = run_dir / "state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"No run state found for run_id '{run_id}' at {state_file}")

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ResearchState.model_validate(data)

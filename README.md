# MarketMind AI — Autonomous Business Research Agent
**Course:** Agentic AI / Applied LLM Systems (AAI-412 / PRAC-05)  
**Stack:** Python 3.10+ | Official OpenAI SDK | Pydantic v2 | Rich CLI  
**Architecture:** Zero-Framework Bounded Plan-Act-Observe Loop with Epistemic Claim Typing and Adversarial Quality Control  

---

## 1. Overview
MarketMind AI is an autonomous, production-grade business intelligence research agent built for management consultancies (Verity Strategy Partners). It transforms ambiguous, natural language market inquiries into rigorous, schema-validated intelligence briefs.

Unlike naive LLM wrappers or mega-prompts that hallucinate citations and blur guesses into facts, MarketMind AI enforces:
- **Zero Agent Frameworks:** Entire plan-act-observe loop, dispatcher, and state machine implemented natively in pure Python.
- **Strict Two-Boundary Security:** All model outputs pass schema validation before execution; all retrieved content is treated as untrusted passive data.
- **Granular Epistemic Typing:** Every single claim is typed as `fact`, `inference`, `recommendation`, or `uncertainty`. Facts require resolvable evidence IDs.
- **Adversarial Quality Control:** Deterministic code checks for unsupported claims, missing sources, and coverage gaps, coupled with a bounded repair loop.
- **Mandatory Human-in-the-Loop Gate:** A 2-minute decision interface presenting assumptions, QC defects, and limitations *before* draft review. No auto-approval or default-yes allowed.

---

## 2. Prerequisites
- **Python:** Version 3.10, 3.11, 3.12, or 3.13.
- **Virtual Environment:** Recommended (`venv` or `conda`).
- **OpenAI API Key (Optional for Mock Mode):** If running with live OpenAI models (`gpt-4o` / `gpt-4o-mini`), a valid API key is required. If running offline, MarketMind includes a deterministic mock mode (`MOCK_MODE=true` or `--mock`) that runs completely without external API connectivity.

---

## 3. Quickstart & Setup

### 3.1 Clone & Environment Setup
```bash
# Clone the repository
git clone <repo-url>
cd Marketmind

# Create and activate a clean virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat

# Install pinned dependencies
pip install -r requirements.txt
```

### 3.2 Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your settings (or use default mock mode):
```ini
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MOCK_MODE=false
RUN_BUDGET_CEILING_USD=3.00
```
*(Note: If `OPENAI_API_KEY` is omitted, MarketMind automatically falls back to deterministic mock execution to prevent runtime crashes).*

### 3.3 Task 01 API Smoke Verification
Verify your configuration, API client resilience, token usage accounting, and masked key display:
```bash
python -m src.main --smoke
# or
python src/main.py --smoke
```

---

## 4. How to Run MarketMind AI

### 4.1 Launch Interactive Web Frontend (Streamlit)
MarketMind AI features a modern executive web dashboard equipped with an **API Key Authentication Entrance Gate**, real-time pipeline visualization, interactive Human Approval Gate, and Section 11 Evaluation Dashboard:

```bash
streamlit run app.py
```
1. When launched, you are greeted by the **Secure Console Access Gate**:
   - Provide your OpenAI API Key (`sk-...`), OR
   - Select **"Offline Deterministic Mock Mode"** to run immediately without an API key or incurring costs.
2. Once authenticated, access the full interactive research console to run scenarios, inspect evidence, audit quality control, and certify publication.

### 4.2 Interactive CLI Mode (Consultant Review Workflow)
Execute a full research brief for Scenario S1 via the command line:
```bash
python src/main.py --scenario S1
```
The system will:
1. Interrogate request for ambiguity and extract scope assumptions.
2. Generate an inspectable research plan (3-6 objectives, 2-5 sub-questions).
3. Execute the bounded research loop across tools (`search_information`, `retrieve_document`, `calculate_metric`).
4. Assemble competitor matrix across 8 vendors with explicit `NOT_ESTABLISHED` markers.
5. Synthesize strategic findings with strict epistemic typing.
6. Run the adversarial QC pass (triggering repair if defects exist).
7. Present the **Human Approval Gate** in your terminal for explicit sign-off:
   - `[1] Approve & Publish`
   - `[2] Reject & Archive`
   - `[3] Request Additional Research`
   - `[4] Modify Scope`
8. Write the published report and serialised state to `runs/<run_id>/`.

### Automated / Non-Interactive Run
To run without interactive prompts (for CI/CD or automated pipelines):
```bash
python src/main.py --scenario S1 --mock --auto-approve "lead.analyst@verity.com"
```

---

## 5. How to Run Tests & Evaluation

### 5.1 Run the 18-Case Conformance Suite & Section 11 Framework
Executes all 18 test cases (T-01 to T-18) with 3 repeat trials on all failure cases, generating the 100-point evaluation breakdown:
```bash
python evaluation/run_eval.py
```
Output reports are generated at:
- `evaluation/results/test_results_summary.md` (Per-case verdicts, repeat counts, fault attributions)
- `evaluation/results/evaluation_report.md` (Nine-dimension evaluation scores)

### 5.2 Run All Unit Tests
Executes the complete test suite verifying dispatcher validation, stuck loops, budget ceilings, QC defect injections, and approval paths:
```bash
python -m unittest discover tests
```

---

## 6. Environment Variable Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `OPENAI_API_KEY` | String | None | OpenAI project-scoped API key (masked on display). |
| `OPENAI_BASE_URL` | String | `None` | Custom API proxy base URL (optional). |
| `MOCK_MODE` | Boolean | `false` | Enable deterministic offline mock execution without external API calls. |
| `PLANNING_MODEL` | String | `gpt-4o` | Model used for research planning stage. |
| `PLANNING_TEMP` | Float | `0.2` | Sampling temperature for planning stage. |
| `RESEARCHER_MODEL` | String | `gpt-4o` | Model used for autonomous agent research loop. |
| `RESEARCHER_TEMP` | Float | `0.1` | Sampling temperature for researcher tool selection. |
| `EVIDENCE_ANALYST_MODEL` | String | `gpt-4o-mini` | Model used for evidence extraction & classification. |
| `EVIDENCE_ANALYST_TEMP` | Float | `0.0` | Zero temperature for deterministic evidence thresholding. |
| `SYNTHESIS_MODEL` | String | `gpt-4o` | Model used for strategic cross-objective synthesis. |
| `SYNTHESIS_TEMP` | Float | `0.3` | Moderate temperature for analytical prose synthesis. |
| `QC_MODEL` | String | `gpt-4o` | Model for independent adversarial quality auditing. |
| `QC_TEMP` | Float | `0.0` | Zero temperature for rigid quality control. |
| `REPORT_GENERATOR_MODEL`| String | `gpt-4o-mini` | Model for final report formatting and rendering. |
| `MAX_ITERATIONS` | Integer | `15` | Maximum agent loop iterations per run. |
| `MAX_TOOL_CALLS` | Integer | `30` | Hard cap on total tool calls per run. |
| `RUN_BUDGET_CEILING_USD`| Float | `3.00` | Cumulative token spend ceiling in USD. |
| `MAX_REPAIR_ROUNDS` | Integer | `2` | Maximum quality control repair iterations. |
| `REQUEST_TIMEOUT_SECONDS`| Float | `45.0` | Network request timeout. |
| `MAX_RETRIES` | Integer | `3` | Maximum exponential backoff retries on transient 429/5xx errors. |
| `LOG_LEVEL` | String | `INFO` | Console and file logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 7. Project Structure & Deliverables

```
marketmind/
├── README.md                           # Master setup, quickstart & documentation (Deliverable 2)
├── requirements.txt                    # Pinned core dependencies
├── .env.example                        # Documented environment template (Deliverable 3)
├── .gitignore                          # Excludes secrets, caches, and runs/
├── src/
│   ├── config.py                       # Validated settings object; model & budget caps (Task 01)
│   ├── llm/
│   │   ├── client.py                   # API client wrapper: backoff, jitter, timeouts, mock
│   │   └── usage.py                    # Token & cost accounting per call (Task 01)
│   ├── schemas/
│   │   ├── plan.py                     # Research plan schema & invariant validator (Task 03)
│   │   ├── evidence.py                 # Evidence & claim schemas (Section 6.2, Task 07)
│   │   ├── report.py                   # Final report schema & cross-field validator (Section 6.1)
│   │   └── tools.py                    # Tool schemas & abuse analysis (Section 5.4, Deliverable 5)
│   ├── agents/
│   │   ├── request_analyser.py         # Request intake, scope & ambiguity extraction (Task 04)
│   │   ├── planner.py                  # Structured research planning (Task 04)
│   │   ├── researcher.py               # Bounded plan-act-observe agent loop (Task 06)
│   │   ├── evidence_analyst.py         # Sceptical gatekeeper & conflict detector (Task 07)
│   │   ├── comparison.py               # Entity x attribute matrix compiler (Section 4.1)
│   │   ├── synthesis.py                # Cross-objective finding synthesizer (Section 4.1)
│   │   ├── quality_control.py          # Adversarial auditor for 5 defect classes (Task 08)
│   │   └── report_generator.py         # Schema-validated report assembler (Task 10)
│   ├── tools/
│   │   ├── registry.py                 # Tool registry with permissions & budgets (Task 05)
│   │   ├── dispatcher.py               # 9-step pipeline: validate, authorise, execute, log
│   │   └── impl/                       # 6 tool implementations (search, retrieve, calc, comp, save, rep)
│   ├── state/
│   │   ├── research_state.py           # Central serializable state object (Task 06)
│   │   └── persistence.py              # Save / resume run artifacts under runs/<run_id>/
│   ├── approval/cli_gate.py            # Human-in-the-loop 4-outcome review gate (Task 09)
│   ├── prompts/                        # Versioned prompts for all 8 agents (Task 01)
│   └── main.py                         # CLI entry point & full orchestration
├── corpus/                             # Curated local corpus (24 documents, planted gap, planted conflict)
│   ├── index.json                      # Document index and planted item annotations
│   └── DOC-*.txt                       # Verified vendor docs, pricing sheets, and analyst reports
├── evaluation/
│   ├── test_cases.json                 # Complete 18-case test suite (T-01 to T-18, Deliverable 7)
│   ├── run_eval.py                     # Evaluation harness & Section 11 scorer
│   └── results/                        # Evaluation report (Deliverable 8) & test summary
├── docs/
│   ├── api_verification.md             # Current API verification audit & date (Deliverable 11)
│   ├── architecture.md                 # Implementation architecture & trust boundaries (Deliverable 4)
│   ├── tool_schemas.md                 # All 6 tool contracts & Section 5.4 abuse analysis (Deliverable 5)
│   ├── technical_documentation.md      # 6-10 page comprehensive engineering report (Deliverable 11)
│   ├── capstone_enterprise_platform.md # Section 16 Enterprise Platform Capstone (R1-R6)
│   ├── viva_answers.md                 # Complete defense answers to all 25 viva questions (Section 15)
│   ├── final_report_S1.md              # Complete human-approved report on S1 + 5-claim spot check (Deliverable 10)
│   ├── schemas/                        # JSON schema files for plan, evidence, report (Deliverable 6)
│   └── screenshots/                    # Operational walkthrough evidence (Deliverable 9)
├── tests/                              # Unit tests (config, dispatcher, evidence, QC, loop)
└── package_submission.py               # Script to package clean <RollNo>_MarketMind.zip archive
```

---

## 8. Known Limitations
1. **Corpus Scope:** The current offline corpus covers 8 primary vendors in the AI customer support software domain (Scenario S1). Expanding to other domains (e.g. S2, S3) requires populating additional verified documents into `corpus/`.
2. **Context Window vs Slicing Trade-off:** While per-question context slicing successfully eliminates context explosion, synthesis requires relying on the Evidence Store references rather than reading all full-text documents in a single prompt.
3. **Reasoning Stylistic Variance:** While factual extraction is deterministic ($T=0.0$), strategic opportunity formulation ($T=0.3$) exhibits minor stylistic phrasing differences across independent runs.

# MarketMind Enterprise — Autonomous Research Platform
**Document:** Section 16 Capstone Architecture & Executive Pitch  
**Audience:** Managing Partner & Head of Technology, Verity Strategy Partners  
**Status:** Architectural Blueprint & Production Roadmap  

---

## Executive Presentation: The Four Fundamental Questions

### 1. How do we know a brief is right?
Through **structural verification, not fluency**. In MarketMind Enterprise, a brief is not considered valid because the prose sounds authoritative. It is verified because:
- Every factual claim binds to an atomic `EvidenceRecord` possessing a cryptographic hash of the raw tool execution result.
- Every citation must resolve through deterministic referential integrity checks.
- Cross-field code invariants verify that no ungrounded claims reach the document.
- The brief passed an independent, adversarial Quality Control audit before reaching the human gate.

### 2. What happens when it is wrong?
The system fails visibly and transparently rather than silently laundering inferences into facts:
- If evidence is conflicting, both sides are surfaced and the claim is classified as `uncertainty`.
- If information is missing from the corpus, the attribute is explicitly stamped `NOT_ESTABLISHED`.
- If QC detects an unsupported claim, the repair loop triggers targeted research questions.
- If the human reviewer rejects the report, publication is aborted, the run is archived with the logged defect reason, and zero client-facing artifacts are emitted.

### 3. What does it cost per brief?
- **AI Token & Infrastructure Cost:** \$0.15 to \$0.45 per brief (leveraging tiered model selection and prompt caching).
- **Human Verification Effort:** 8 to 12 billable hours of senior analyst review (reduced from 28–40 hours of manual drafting).
- **Internal Production Cost:** \$950 – \$1,350 total per brief, billed at \$8,000 – \$12,000, raising practice gross margins from 68% to over 88%.

### 4. Who is accountable when a client acts on a bad one?
**A named human partner.** The system never publishes autonomously. Every published report incorporates an immutable cryptographic `ApprovalRecord` identifying the partner who certified the findings, the timestamp, and their explicit review notes. Legal liability remains strictly human.

---

## R1 — Multi-Tenant Request Handling at Scale

### Request Queuing & Prioritization
- **Architecture:** Celery / Redis-backed distributed task queue partitioned into three priority tiers:
  1. *Priority 1 (Urgent Client Commissions):* Guaranteed execution start within 30 seconds; dedicated worker pool.
  2. *Priority 2 (Standard Engagements):* First-in, first-out queueing with fair-share scheduling.
  3. *Priority 3 (Background Corpus Refresh / Regression Evals):* Low-priority batch processing during off-peak hours.

### Run Isolation & Data Sovereignty
- **Multi-Tenant Partitioning:** Strict logical and storage isolation. Each client engagement runs in an isolated workspace container with its own ephemeral evidence store. One client's private diligence documents or commissioned research can never leak into another client's report or corpus.
- **Provider Concurrency & Rate Limits:** OpenAI tier-5 rate limits (10,000 requests/min, 5M TPM). The system manages a central token-bucket rate limiter enforcing per-tenant quotas and preventing worker starvation.

### Resumability & Worker Failure Handling
- **State Serialization:** Research state is persisted to PostgreSQL / S3 at every loop iteration and after every tool execution.
- **Crash Recovery:** If a worker node crashes mid-run, a heartbeat monitor detects worker death within 15 seconds. An idle worker claims the serialized run ID, reads `state.json`, resumes from the exact open sub-question without repeating paid tool calls, and preserves all previously collected evidence.

---

## R2 — A Governed Tool Ecosystem

### Tool Onboarding & Verification Gate
To scale beyond hard-coded functions, all new tools must progress through a formal Governance Gate:
1. **Schema Strictness:** Must define strict JSON Schemas with bounded numeric ranges, regex string constraints, and closed enums. Additional properties must be forbidden.
2. **Permission Boundary Assignment:**
   - *Read-Class:* Information lookup without side-effects (e.g. SEC EDGAR API, PubMed, Patent DB).
   - *Compute-Class:* Pure Python deterministic arithmetic without network or disk mutation.
   - *Write-Class:* Side-effecting operations (e.g. creating research tickets, saving evidence). Write tools require explicit role-based permissions and are restricted to designated stages.
3. **Reproducibility Tracking:** Every tool is versioned (e.g. `search_sec:v2.1.0`). Reports store the exact tool versions used during execution to guarantee forensic audit reproducibility.
4. **Deprecation Policy:** Tools marked for deprecation enter a 90-day grace period where downstream callers receive automated warnings in the run log.

---

## R3 — Institutional Research Memory

### Accumulating & Reusing Research Assets
With Verity producing 14+ briefs monthly, previously gathered evidence represents a significant proprietary asset.
- **Evidence Indexing:** Validated evidence records are stored in a centralized vector and relational store (PostgreSQL + pgvector), tagged by entity, topic, date, and confidence.
- **Staleness Policy & Re-validation:**
  - *Pricing Data:* Max age 60 days. Stale pricing triggers mandatory re-verification before reuse.
  - *Market Sizing / Historical Filings:* Max age 180 days.
  - *Regulatory Statutes:* Max age 90 days.
- **Attribution & Lineage:** Reused evidence is visibly tagged in the report appendix as `[REUSED from Brief #2025-Q3, Verified 2026-01]`. Silent reuse is strictly prohibited.
- **Error Propagation:** If an evidence record is marked erroneous or corrected by an analyst, a dependency graph identifies all historical briefs citing that record and alerts the account leads.

---

## R4 — Quality Assurance & Continuous Evaluation

### Automated Regression Pass Bar
Every prompt revision, schema modification, tool release, or model update must pass an automated CI/CD pipeline blocking release if:
- Schema validation pass rate drops below 100%.
- Hallucination rate on adversarial probes (e.g. non-existent vendor test T-09) exceeds 0.0%.
- Contradiction detection sensitivity drops below 95%.
- Cumulative cost per run exceeds budget thresholds.

### Online Quality Signals & Incident Response
- **Decay Signals:** Central Datadog dashboard tracking:
  1. *Approval Gate Rejection Rate:* Alert if $> 15\%$.
  2. *Reviewer Edit Distance:* Alert if human reviewers rewrite $> 20\%$ of synthesized text.
  3. *QC Defect Spike:* Alert if average repair rounds $> 1.4$.
- **Incident Response Runbook:** If a published brief is found to contain a material defect, an immediate post-mortem is triggered: the run's full `state.json` and tool log are isolated to diagnose whether planning, retrieval, or synthesis failed, and regression test cases are updated within 24 hours.

---

## R5 — Human Oversight as an Operating Model

### Reviewer Hierarchy & Authority Levels
- **Associate Analyst:** Authorized to review evidence stores, resolve targeted gap questions, and recommend approval.
- **Senior Engagement Manager:** Authorized to approve and publish mid-market briefs.
- **Practice Managing Partner:** Mandatory sign-off required for:
  1. Private-equity M&A acquisition shortlists.
  2. Any brief containing high-severity market contradictions.
  3. Strategic recommendations involving investments $> \$5M$.

### Anti-Complacency UI Design
To prevent reviewers from treating the approval gate as a rubber stamp:
- The interface enforces a mandatory minimum review engagement time based on brief length.
- The 2-minute decision summary surfaces outstanding defects and limitations *before* displaying full text.
- Random sampling audits: 10% of approved briefs undergo blind secondary review by the Practice Quality Director.

---

## R6 — Cost, Reliability & The Business Case

### Unit Economics Model (14 Briefs Rising to 40 Briefs/Month)

| Metric | Traditional Manual Baseline | MarketMind Enterprise (14 Briefs) | MarketMind Enterprise (40 Briefs at Scale) |
| :--- | :--- | :--- | :--- |
| **Elapsed Turnaround Time** | 2–3 weeks | 2–3 business days | 24–48 hours |
| **Analyst Effort per Brief** | 28–40 hours | 8–12 hours | 6–8 hours |
| **Internal Cost per Brief** | \$2,700 – \$3,800 | \$950 – \$1,350 | \$680 – \$920 |
| **Platform / Model Compute Cost** | \$0.00 | \$0.35 per brief | \$0.18 per brief (caching + tiering) |
| **Practice Gross Margin** | 68% | 88.5% | 92.1% |
| **Annual Practice Net Profit** | \$1.05M | \$1.62M | \$4.85M |

### The Core Business Case
Implementing MarketMind Enterprise unlocks immediate capacity expansion without linear analyst hiring. By automating mechanical source collection, comparative tabulation, and citation verification while preserving rigorous human governance, Verity Strategy Partners transforms from a capacity-constrained consultancy into an agile, high-margin market intelligence powerhouse.

# MarketMind AI — Tool System & Security Specification
**Document:** Deliverable 5 / Section 5 & Section 10  
**Status:** Certified & Implemented  

---

## 1. Tool Design Contract Overview
Every tool in MarketMind AI declares:
- **Name:** Stable, verb-led, unambiguous.
- **Description:** Written for the model to steer tool selection.
- **Argument Schema:** Strict JSON Schema with bounded values, enums, and disallowed additional properties (`additionalProperties: false`).
- **Permission Level:** `read`, `compute`, `write`. Write-class tools are strictly prohibited outside designated stages.
- **Result Contract:** Deterministic dictionary with `status: "success"` or structured `status: "error"` containing error type and guidance.
- **Cost & Limits:** Hard call budgets and timeouts enforced by the Dispatcher.

---

## 2. Comprehensive Tool Catalog & Schemas

### Tool 1: `search_information`
- **Permission:** `read`
- **Call Budget:** 40 calls per run | **Timeout:** 10.0 seconds
- **Allowed Stages:** `researcher`, `quality_control`, `synthesis`
- **Description:** Search approved knowledge base and local corpus for matching text snippets.
- **Argument Schema:**
  - `query` (string, 3–200 characters, required)
  - `source_type` (enum: `all`, `vendor_doc`, `pricing_page`, `analyst_report`, `press_release`, required)
  - `max_results` (integer, bounded 1–20, required)
  - `recency_window` (enum: `1y`, `3y`, `5y`, `any`, required)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* An attacker passes an unbounded integer (`max_results: 10000`) or memory-flooding query to induce denial of service.
  - *Prevention Mechanism:* Strict JSON Schema validation rejecting `max_results > 20`, capping query length at 200 characters, and restricting filters to closed enums.

---

### Tool 2: `retrieve_document`
- **Permission:** `read`
- **Call Budget:** 30 calls per run | **Timeout:** 10.0 seconds
- **Allowed Stages:** `researcher`, `quality_control`, `synthesis`
- **Description:** Retrieve full verified text and metadata of a specific indexed document.
- **Argument Schema:**
  - `document_id` (string, regex `^[A-Za-z0-9_-]+$`, required)
  - `section` (string or null, optional)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* An attacker utilizes directory traversal (`../../etc/passwd` or `file:///C:/...`) to read sensitive host environment secrets.
  - *Prevention Mechanism:* Strict regex pattern forbidding slashes, dots, and colons; dispatcher validates `document_id` against the verified in-memory corpus index allow-list prior to filesystem access.

---

### Tool 3: `calculate_metric`
- **Permission:** `compute`
- **Call Budget:** 20 calls per run | **Timeout:** 5.0 seconds
- **Allowed Stages:** `researcher`, `synthesis`, `quality_control`
- **Description:** Perform deterministic mathematical arithmetic in Python.
- **Argument Schema:**
  - `operation` (enum: `growth_rate`, `cagr`, `share`, `ratio`, `average`, `sum`, `difference`, required)
  - `values` (array of numbers, 1–50 items, required)
  - `period` (number or null, bounded 0.01–100.0, optional)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* An attacker executes arbitrary Python code execution via free-form mathematical evaluation strings (e.g. `eval("__import__('os').system('...')")`).
  - *Prevention Mechanism:* Absolutely no `eval()` or `exec()` in the codebase; closed enum of 7 mathematical operations with pure Python arithmetic and zero-division guards.

---

### Tool 4: `compare_companies`
- **Permission:** `compute`
- **Call Budget:** 15 calls per run | **Timeout:** 8.0 seconds
- **Allowed Stages:** `researcher`, `comparison`, `synthesis`
- **Description:** Construct an entity by attribute comparative matrix strictly from stored evidence records.
- **Argument Schema:**
  - `entities` (array of strings, max 10 items, required)
  - `attributes` (array of enums: `pricing_model`, `starting_price`, `enterprise_tier`, `core_features`, `integrations`, `compliance`, `target_segment`, required)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* The model attempts to hallucinate missing vendor data to produce an aesthetically complete matrix.
  - *Prevention Mechanism:* Strict code-level enforcement: any cell lacking a verified `evidence_id` in the run's Evidence Store is returned as `NOT_ESTABLISHED`. No interpolation or guessing permitted.

---

### Tool 5: `save_research`
- **Permission:** `write`
- **Call Budget:** 50 calls per run | **Timeout:** 5.0 seconds
- **Allowed Stages:** `researcher`, `quality_control`, `synthesis`
- **Description:** Persist an atomic evidence record into the run's Evidence Store.
- **Argument Schema:**
  - `question_id` (string, required)
  - `claim` (string, 5–500 characters, required)
  - `claim_type` (enum: `fact`, `inference`, `recommendation`, `uncertainty`, required)
  - `source_ref` (string, required)
  - `confidence` (enum: `high`, `medium`, `low`, required)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* The model hallucinates an authoritative claim and fabricates an untraceable citation reference.
  - *Prevention Mechanism:* Deterministic referential integrity check: `source_ref` MUST match a real prior tool execution result ID or indexed document ID in `state.tool_history`. Untraceable records are strictly rejected and logged in `rejection_log`.

---

### Tool 6: `generate_report`
- **Permission:** `write`
- **Call Budget:** 5 calls per run | **Timeout:** 15.0 seconds
- **Allowed Stages:** `synthesis`, `report_generator`
- **Description:** Assemble draft report from active Evidence Store and Plan.
- **Argument Schema:**
  - `run_id` (string, required)
  - `sections` (array of strings or null, optional)
- **Abuse Analysis (Section 5.4):**
  - *Abuse Scenario:* An unauthorized agent stage or compromised tool call triggers autonomous report publication without human oversight.
  - *Prevention Mechanism:* Permission boundary blocks execution in non-reporting stages; `generate_report` only produces a draft report object; final publication strictly requires execution of the interactive `HumanApprovalGate`.

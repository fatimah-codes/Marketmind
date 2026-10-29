# MarketMind AI — Official API Verification & Compliance Audit
**Course:** Agentic AI / Applied LLM Systems (AAI-412 / PRAC-05)  
**Date of Audit & Verification:** October 2026 / Verified against OpenAI API Reference v1.59+  
**Auditor:** Lead Systems Architect / MarketMind Engineering Team  

---

## 1. Executive Summary & Audit Mandate
Per Task 01 and Deliverable 11 of the assignment specification, all API call patterns, parameters, tool definitions, structured output mechanisms, and pricing formulas must be verified against current official documentation. Legacy assumptions, stale pseudocode, and deprecated endpoints (e.g., legacy `functions` parameter, untyped responses, unhandled rate-limit headers) are strictly forbidden and penalized under OpenAI Integration.

This document formally records the API surfaces verified, the exact parameter names utilized, differences between initial assumptions and current API realities, and the engineering mitigations deployed.

---

## 2. API Surface Verification Matrix

| Capability | Verified Current API Parameter / Method | Deprecated / Stale Pattern (Avoided) | Official Documentation Source |
| :--- | :--- | :--- | :--- |
| **Tool Calling Definition** | `tools=[{"type": "function", "function": {"name": ..., "description": ..., "parameters": ..., "strict": true}}]` | `functions=[...]` (deprecated since 2023) | `/docs/guides/function-calling` |
| **Tool Choice** | `tool_choice="auto"` or `tool_choice={"type": "function", "function": {"name": ...}}` | `function_call="auto"` | `/docs/guides/function-calling` |
| **Structured Outputs** | `response_format={"type": "json_schema", "json_schema": {"name": ..., "strict": true, "schema": ...}}` or `client.beta.chat.completions.parse(...)` | Raw JSON prompting (`response_format={"type": "json_object"}`) without schema guarantees | `/docs/guides/structured-outputs` |
| **Tool Call Return Shape** | `response.choices[0].message.tool_calls` containing list of `ChatCompletionMessageToolCall(id, type='function', function=Function(name, arguments))` | Single `function_call` property on message | `/docs/api-reference/chat/object` |
| **Tool Result Submission** | Message with `role="tool"`, `tool_call_id=tool_call.id`, `content=str(result_json)` | `role="function"`, `name=tool_name` | `/docs/guides/function-calling` |
| **Parallel Tool Calls** | Enabled by default; can be explicitly toggled via `parallel_tool_calls=True/False` | Manual iterative single-call loop assumptions | `/docs/guides/function-calling#parallel-function-calling` |
| **Rate Limit Headers** | Standard RFC headers: `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`, `retry-after` | Fixed hard-coded sleep timers | `/docs/guides/rate-limits` |
| **Current Models** | `gpt-4o` (flagship reasoning), `gpt-4o-mini` (cost-optimized extraction/formatting) | `gpt-4-turbo-preview`, `gpt-3.5-turbo` | `/docs/models` |

---

## 3. Detailed Differences Identified & Architectural Decisions

### 3.1 Strict Schema Constraints in Structured Outputs & Tool Calling
- **Observation:** When setting `"strict": true` in OpenAI structured outputs and tool definitions, OpenAI's grammar-constrained decoding engine enforces strict JSON Schema subsets:
  1. Every property in an object's `properties` dictionary must be explicitly listed in the `required` array.
  2. The schema must set `"additionalProperties": false`.
  3. Optional fields must be expressed as type unions with `null` (e.g., `{"type": ["string", "null"]}`), not by omitting them from `required`.
  4. Recursive schemas and certain complex regex patterns have depth/validation limits.
- **Architectural Mitigation:**
  MarketMind implements a schema normalizer in `src/schemas/tools.py` and `src/schemas/report.py` ensuring that all Pydantic models automatically export strict-compliant schemas with explicit required lists and `additionalProperties: false`.

### 3.2 Parallel Tool Execution Behavior
- **Observation:** Models (`gpt-4o`) frequently emit multiple tool calls in a single turn (e.g., searching for three competitors simultaneously). A naive sequential dispatcher would lose subsequent calls or fail to bind results to corresponding `tool_call_id`s.
- **Architectural Mitigation:**
  `src/agents/researcher.py` and `src/tools/dispatcher.py` explicitly iterate over all `tool_calls` in `message.tool_calls`, dispatch each independently, attach corresponding `tool_call_id`s, and return a batch of tool messages back to the conversation state.

### 3.3 Rate Limit Handling & Jitter
- **Observation:** Calling APIs aggressively during multi-agent loops can trigger HTTP 429 (`RateLimitError`). Immediate retries amplify server load and fail repeatedly under concurrency.
- **Architectural Mitigation:**
  `src/llm/client.py` inspects the HTTP response. If a `retry-after` header is present, it sleeps for that duration. Otherwise, it implements full exponential backoff with decorrelated jitter ($delay = \min(max\_backoff, initial\_backoff \times 2^{attempt} + random.uniform(0, 0.5))$).

### 3.4 Cost Accounting Surface
- **Observation:** Modern responses provide granular token breakdown in `completion.usage`, including `prompt_tokens`, `completion_tokens`, and `prompt_tokens_details.cached_tokens`.
- **Architectural Mitigation:**
  `src/llm/usage.py` accurately deducts cached token rates where applicable and maintains per-stage, per-call, and cumulative run budgets.

---

## 4. Current Pricing Table (Used in Accounting Engine)
Verified rates as of current documentation:

| Model ID | Input Tokens (per 1M) | Cached Input (per 1M) | Output Tokens (per 1M) |
| :--- | :--- | :--- | :--- |
| `gpt-4o` | \$2.50 | \$1.25 | \$10.00 |
| `gpt-4o-mini` | \$0.15 | \$0.075 | \$0.60 |

---

## 5. Verification Sign-Off
- **Status:** Verified and fully compliant.
- **Framework Constraint:** Zero third-party agent orchestration frameworks utilized. All loops, tool dispatching, schema validations, and state machines are implemented natively in pure Python 3.10+.

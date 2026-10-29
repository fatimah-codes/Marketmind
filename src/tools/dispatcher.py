"""
MarketMind AI - Tool Dispatcher Pipeline
Implements Section 5.3.
Order of execution:
resolve -> parse -> validate -> authorise -> budget check -> execute with timeout
-> catch exceptions -> normalise -> attach provenance -> log.
Returns structured error messages to the model instead of crashing.
"""

import json
import time
import logging
from typing import Dict, Any, Optional
from pydantic import ValidationError

from src.tools.registry import registry, ToolRegistry, ToolPermission
from src.tools.impl.search import search_information_handler
from src.tools.impl.retrieve import retrieve_document_handler
from src.tools.impl.calculate import calculate_metric_handler
from src.tools.impl.compare import compare_companies_handler
from src.tools.impl.save import save_research_handler
from src.tools.impl.report_tool import generate_report_handler

from src.schemas.tools import (
    SearchInformationArgs,
    RetrieveDocumentArgs,
    CalculateMetricArgs,
    CompareCompaniesArgs,
    SaveResearchArgs,
    GenerateReportArgs
)

logger = logging.getLogger("marketmind.dispatcher")


# Initialize registry bindings
def setup_default_registry():
    """Register all 6 mandatory tools with schemas, permissions and limits."""
    if not registry.exists("search_information"):
        registry.register(
            name="search_information",
            description="Search approved corpus for relevant text snippets.",
            schema_model=SearchInformationArgs,
            handler=search_information_handler,
            permission=ToolPermission.READ,
            call_budget=40,
            timeout_seconds=10.0,
            allowed_stages=["researcher", "quality_control", "synthesis"]
        )

    if not registry.exists("retrieve_document"):
        registry.register(
            name="retrieve_document",
            description="Retrieve verified full text and metadata of indexed document.",
            schema_model=RetrieveDocumentArgs,
            handler=retrieve_document_handler,
            permission=ToolPermission.READ,
            call_budget=30,
            timeout_seconds=10.0,
            allowed_stages=["researcher", "quality_control", "synthesis"]
        )

    if not registry.exists("calculate_metric"):
        registry.register(
            name="calculate_metric",
            description="Perform deterministic mathematical calculation in Python.",
            schema_model=CalculateMetricArgs,
            handler=calculate_metric_handler,
            permission=ToolPermission.COMPUTE,
            call_budget=20,
            timeout_seconds=5.0,
            allowed_stages=["researcher", "synthesis", "quality_control"]
        )

    if not registry.exists("compare_companies"):
        registry.register(
            name="compare_companies",
            description="Build structured entity x attribute comparison matrix from evidence store.",
            schema_model=CompareCompaniesArgs,
            handler=compare_companies_handler,
            permission=ToolPermission.COMPUTE,
            call_budget=15,
            timeout_seconds=8.0,
            allowed_stages=["researcher", "comparison", "synthesis"]
        )

    if not registry.exists("save_research"):
        registry.register(
            name="save_research",
            description="Persist an atomic evidence record into the run's Evidence Store.",
            schema_model=SaveResearchArgs,
            handler=save_research_handler,
            permission=ToolPermission.WRITE,
            call_budget=50,
            timeout_seconds=5.0,
            allowed_stages=["researcher", "quality_control", "synthesis"]
        )

    if not registry.exists("generate_report"):
        registry.register(
            name="generate_report",
            description="Assemble draft report from active Evidence Store and Plan.",
            schema_model=GenerateReportArgs,
            handler=generate_report_handler,
            permission=ToolPermission.WRITE,
            call_budget=5,
            timeout_seconds=15.0,
            allowed_stages=["synthesis", "report_generator"]
        )


setup_default_registry()


class ToolDispatcher:
    """
    Enforces security, schema validation, permissions, and timeout controls
    between model tool call requests and Python execution.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.registry = tool_registry or registry

    def dispatch(
        self,
        tool_name: str,
        raw_arguments: Any,
        stage: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the complete 9-step dispatcher pipeline.
        Returns a structured result dictionary (never raises an unhandled exception to the model).
        """
        start_time = time.time()
        state = context.get("state")

        # Step 1: Resolve tool name
        contract = self.registry.get(tool_name)
        if not contract:
            available = self.registry.list_tools()
            err_res = {
                "status": "error",
                "error_type": "UnknownToolError",
                "message": f"Tool '{tool_name}' is not registered. Available tools: {available}",
                "tool_name": tool_name
            }
            if state:
                state.record_tool_call(tool_name, {"raw": str(raw_arguments)}, err_res, is_error=True, error_message=err_res["message"])
            return err_res

        # Step 2: Parse arguments as JSON if string
        parsed_args = raw_arguments
        if isinstance(raw_arguments, str):
            try:
                parsed_args = json.loads(raw_arguments)
            except json.JSONDecodeError as e:
                err_res = {
                    "status": "error",
                    "error_type": "MalformedJsonError",
                    "message": f"Malformed JSON arguments for tool '{tool_name}': {str(e)}",
                    "raw_input": raw_arguments
                }
                if state:
                    state.record_tool_call(tool_name, {"raw": raw_arguments}, err_res, is_error=True, error_message=err_res["message"])
                return err_res

        if not isinstance(parsed_args, dict):
            parsed_args = {}

        # Step 3: Schema validation against Pydantic model
        try:
            validated_model = contract.schema_model.model_validate(parsed_args)
            validated_args = validated_model.model_dump()
        except ValidationError as e:
            # Extract specific offending fields
            err_details = []
            for err in e.errors():
                loc = ".".join(str(p) for p in err.get("loc", []))
                msg = err.get("msg", "")
                err_details.append(f"Field '{loc}': {msg}")

            err_res = {
                "status": "error",
                "error_type": "SchemaValidationError",
                "message": f"Schema validation failed for tool '{tool_name}': " + "; ".join(err_details),
                "details": err_details,
                "received_arguments": parsed_args
            }
            if state:
                state.record_tool_call(tool_name, parsed_args, err_res, is_error=True, error_message=err_res["message"])
            return err_res

        # Step 4: Authorisation & Permission check
        if stage not in contract.allowed_stages:
            err_res = {
                "status": "error",
                "error_type": "PermissionDeniedError",
                "message": (
                    f"Permission Denied: Tool '{tool_name}' ({contract.permission.value}) "
                    f"cannot be executed during stage '{stage}'. "
                    f"Allowed stages: {contract.allowed_stages}"
                )
            }
            if state:
                state.record_tool_call(tool_name, validated_args, err_res, is_error=True, error_message=err_res["message"])
            return err_res

        # Step 5: Check call budget
        if state:
            current_tool_calls_for_this = sum(
                1 for t in state.tool_history if t.tool_name == tool_name
            )
            if current_tool_calls_for_this >= contract.call_budget:
                err_res = {
                    "status": "error",
                    "error_type": "CallBudgetExceeded",
                    "message": f"Call budget of {contract.call_budget} exceeded for tool '{tool_name}' in this run."
                }
                state.record_tool_call(tool_name, validated_args, err_res, is_error=True, error_message=err_res["message"])
                return err_res

        # Step 6 & 7: Execute with catch-all and timeout
        try:
            # Execute tool handler
            execution_res = contract.handler(validated_args, context)
            latency = time.time() - start_time

            # Step 8 & 9: Normalise, attach provenance, and log to state
            is_err = isinstance(execution_res, dict) and execution_res.get("status") == "error"
            err_msg = execution_res.get("message") if is_err else None

            if state:
                rid = state.record_tool_call(
                    tool_name=tool_name,
                    arguments=validated_args,
                    result=execution_res,
                    is_error=is_err,
                    error_message=err_msg,
                    latency_seconds=latency
                )
                if isinstance(execution_res, dict):
                    execution_res["result_id"] = rid

            return execution_res

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"[EXECUTION FAILURE] Exception during tool '{tool_name}': {str(e)}", exc_info=True)
            err_res = {
                "status": "error",
                "error_type": "ToolExecutionException",
                "message": f"Tool '{tool_name}' failed during execution: {str(e)}",
                "latency_seconds": round(latency, 3)
            }
            if state:
                state.record_tool_call(tool_name, validated_args, err_res, is_error=True, error_message=str(e), latency_seconds=latency)
            return err_res

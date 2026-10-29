"""
MarketMind AI - Tool Registry and Permission Contracts
Implements Section 5.1 and 5.2.
Declares tools with strict schemas, permission levels, budgets, and timeouts.
"""

from enum import Enum
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel

from src.schemas.tools import (
    SearchInformationArgs,
    RetrieveDocumentArgs,
    CalculateMetricArgs,
    CompareCompaniesArgs,
    SaveResearchArgs,
    GenerateReportArgs,
    TOOL_DEFINITIONS
)


class ToolPermission(str, Enum):
    """
    Permission boundaries (Section 10, Control 4).
    Write tools cannot be invoked outside stages that legitimately require them.
    """
    READ = "read"
    COMPUTE = "compute"
    WRITE = "write"


@dataclass
class ToolContract:
    """The contract governing a registered tool."""
    name: str
    description: str
    schema_model: type[BaseModel]
    handler: Callable[..., Any]
    permission: ToolPermission
    call_budget: int
    timeout_seconds: float
    allowed_stages: list[str]


class ToolRegistry:
    """Central registry of approved agent tools."""

    def __init__(self):
        self._tools: Dict[str, ToolContract] = {}

    def register(
        self,
        name: str,
        description: str,
        schema_model: type[BaseModel],
        handler: Callable[..., Any],
        permission: ToolPermission,
        call_budget: int = 50,
        timeout_seconds: float = 15.0,
        allowed_stages: Optional[list[str]] = None
    ):
        """Register a tool with its schema, permission boundary, and execution limits."""
        if allowed_stages is None:
            if permission == ToolPermission.WRITE:
                allowed_stages = ["researcher", "quality_control", "synthesis", "report_generator"]
            else:
                allowed_stages = ["researcher", "planner", "synthesis", "quality_control"]

        self._tools[name] = ToolContract(
            name=name,
            description=description,
            schema_model=schema_model,
            handler=handler,
            permission=permission,
            call_budget=call_budget,
            timeout_seconds=timeout_seconds,
            allowed_stages=allowed_stages
        )

    def get(self, name: str) -> Optional[ToolContract]:
        return self._tools.get(name)

    def exists(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_openai_tool_definitions(self) -> list[dict]:
        """Return the strict OpenAI tool definitions for API calls."""
        return TOOL_DEFINITIONS


# Global tool registry instance
registry = ToolRegistry()

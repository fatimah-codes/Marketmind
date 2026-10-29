"""
MarketMind AI - Tool Schemas and Abuse Analysis
Implements Section 5.1, 5.2, and 5.4.
Strict schemas, enums, bounded numbers, no free-form eval, and adversarial protections.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Tool 1: search_information
# ==========================================
class SourceTypeFilter(str, Enum):
    ALL = "all"
    VENDOR_DOC = "vendor_doc"
    PRICING_PAGE = "pricing_page"
    ANALYST_REPORT = "analyst_report"
    PRESS_RELEASE = "press_release"


class RecencyWindow(str, Enum):
    ONE_YEAR = "1y"
    THREE_YEARS = "3y"
    FIVE_YEARS = "5y"
    ANY = "any"


class SearchInformationArgs(BaseModel):
    """
    Search approved knowledge base and local corpus for matching snippets.
    Never searches open unverified web unless explicitly configured.
    """
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Search keywords or targeted conceptual query"
    )
    source_type: SourceTypeFilter = Field(
        default=SourceTypeFilter.ALL,
        description="Filter by specific source category"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of snippets to return (strictly bounded between 1 and 20)"
    )
    recency_window: RecencyWindow = Field(
        default=RecencyWindow.ANY,
        description="Filter by document publication time horizon"
    )


# ==========================================
# Tool 2: retrieve_document
# ==========================================
class RetrieveDocumentArgs(BaseModel):
    """
    Retrieve complete text and metadata of a verified document from corpus.
    Never accepts arbitrary URLs or local filesystem paths.
    """
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Exact identifier of the indexed document (e.g., 'DOC-ZD-01'). Raw file paths rejected."
    )
    section: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional section header to focus extraction"
    )


# ==========================================
# Tool 3: calculate_metric
# ==========================================
class MetricOperation(str, Enum):
    GROWTH_RATE = "growth_rate"
    CAGR = "cagr"
    SHARE = "share"
    RATIO = "ratio"
    AVERAGE = "average"
    SUM = "sum"
    DIFFERENCE = "difference"


class CalculateMetricArgs(BaseModel):
    """
    Perform deterministic mathematical calculation in Python.
    No model approximations or free-form code evaluation permitted.
    """
    model_config = ConfigDict(extra="forbid")

    operation: MetricOperation = Field(
        ...,
        description="Arithmetic operation from closed enum. Prevents arbitrary expression execution."
    )
    values: List[float] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of numeric inputs to operate upon"
    )
    period: Optional[float] = Field(
        default=None,
        ge=0.01,
        le=100.0,
        description="Number of periods/years for CAGR or annualized growth rates"
    )


# ==========================================
# Tool 4: compare_companies
# ==========================================
class CompanyAttribute(str, Enum):
    PRICING_MODEL = "pricing_model"
    STARTING_PRICE = "starting_price"
    ENTERPRISE_TIER = "enterprise_tier"
    CORE_FEATURES = "core_features"
    INTEGRATIONS = "integrations"
    COMPLIANCE = "compliance"
    TARGET_SEGMENT = "target_segment"


class CompareCompaniesArgs(BaseModel):
    """
    Build structured entity x attribute comparison matrix from evidence store.
    Unestablished cells explicitly flagged as 'NOT_ESTABLISHED'.
    """
    model_config = ConfigDict(extra="forbid")

    entities: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of vendor or entity names to compare (max 10)"
    )
    attributes: List[CompanyAttribute] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="List of attributes to compare from closed enum"
    )


# ==========================================
# Tool 5: save_research
# ==========================================
class SaveResearchArgs(BaseModel):
    """
    Persist an atomic evidence record into the run's Evidence Store.
    Requires an existing, verified tool result ID as source_ref.
    """
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="ID of the research question addressed (e.g. 'Q-101')"
    )
    claim: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Single supported claim"
    )
    claim_type: str = Field(
        ...,
        pattern=r"^(fact|inference|recommendation|uncertainty)$",
        description="Epistemic classification: fact, inference, recommendation, uncertainty"
    )
    source_ref: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="ID of the tool result this came from. Must resolve to a real prior tool execution."
    )
    confidence: str = Field(
        default="medium",
        pattern=r"^(high|medium|low)$",
        description="Confidence level"
    )


# ==========================================
# Tool 6: generate_report
# ==========================================
class GenerateReportArgs(BaseModel):
    """
    Assemble draft report from the active Evidence Store and plan.
    Fails loudly if mandatory evidence is absent.
    """
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        ...,
        description="Current research run ID"
    )
    sections: Optional[List[str]] = Field(
        default=None,
        description="Optional subset of sections to generate"
    )


# ==========================================
# OpenAI Strict Function Definitions
# ==========================================
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_information",
            "description": (
                "Search the approved research corpus for relevant text snippets. "
                "Use this tool when you need empirical information, pricing data, or vendor facts. "
                "Do NOT use this tool to calculate metrics or synthesize final reports. "
                "Returns a list of hits with hit_id, title, source_id, date, and text snippet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or search phrase (3-200 chars)"
                    },
                    "source_type": {
                        "type": "string",
                        "enum": ["all", "vendor_doc", "pricing_page", "analyst_report", "press_release"],
                        "description": "Filter by source type"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max hits to return (1-20)",
                        "minimum": 1,
                        "maximum": 20
                    },
                    "recency_window": {
                        "type": "string",
                        "enum": ["1y", "3y", "5y", "any"],
                        "description": "Time window filter"
                    }
                },
                "required": ["query", "source_type", "max_results", "recency_window"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_document",
            "description": (
                "Retrieve the full verified text and metadata of a specific document by document_id. "
                "Use this tool after finding a relevant hit via search_information to extract complete context. "
                "Do NOT provide arbitrary URLs or filesystem paths; only use valid document_ids from search hits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Exact document ID (e.g. 'DOC-ZD-01')"
                    },
                    "section": {
                        "type": ["string", "null"],
                        "description": "Optional section header"
                    }
                },
                "required": ["document_id", "section"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_metric",
            "description": (
                "Perform accurate mathematical calculations in Python. "
                "Use this tool whenever computing market share, growth rates, CAGR, percentages, or averages. "
                "Never estimate or mentally compute numbers when this tool is available. "
                "Returns exact computed value, mathematical formula, and echoed inputs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["growth_rate", "cagr", "share", "ratio", "average", "sum", "difference"],
                        "description": "Arithmetic operation to execute"
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numeric values to compute"
                    },
                    "period": {
                        "type": ["number", "null"],
                        "description": "Number of periods/years for CAGR or annual calculations"
                    }
                },
                "required": ["operation", "values", "period"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_companies",
            "description": (
                "Construct an entity by attribute comparative matrix strictly from stored empirical evidence. "
                "Use this tool to compare multiple vendors side-by-side across pricing, features, or tiers. "
                "Any cell without verified evidence is marked 'NOT_ESTABLISHED'. "
                "Returns tabular matrix data with evidence provenance IDs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Vendor names to compare (max 10)"
                    },
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "pricing_model",
                                "starting_price",
                                "enterprise_tier",
                                "core_features",
                                "integrations",
                                "compliance",
                                "target_segment"
                            ]
                        },
                        "description": "Attributes to compare"
                    }
                },
                "required": ["entities", "attributes"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_research",
            "description": (
                "Record a verified evidence claim into the persistent Evidence Store. "
                "Use this tool immediately after extracting a factual finding from a tool result. "
                "The source_ref MUST match an existing tool result ID (e.g. 'HIT-01' or 'DOC-ZD-01'). "
                "Unresolvable source_ref calls will be strictly rejected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "string",
                        "description": "ID of the sub-question addressed"
                    },
                    "claim": {
                        "type": "string",
                        "description": "Atomic claim statement"
                    },
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "inference", "recommendation", "uncertainty"],
                        "description": "Epistemic classification"
                    },
                    "source_ref": {
                        "type": "string",
                        "description": "Tool result ID supporting this claim"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Confidence assessment"
                    }
                },
                "required": ["question_id", "claim", "claim_type", "source_ref", "confidence"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Compile and format the final intelligence brief from stored evidence. "
                "Use this tool only when all open research questions have been investigated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Active research run identifier"
                    },
                    "sections": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "description": "Optional list of sections"
                    }
                },
                "required": ["run_id", "sections"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]


# ==========================================
# Section 5.4 Abuse Analysis Mapping
# ==========================================
TOOL_ABUSE_ANALYSIS: Dict[str, Dict[str, str]] = {
    "search_information": {
        "abuse_scenario": "An attacker or compromised context issues an unbounded search (e.g. max_results=10000) or denial-of-service query string flooding the memory.",
        "prevention_mechanism": "Strict JSON Schema bounds: query length capped between 3 and 200 characters; max_results constrained between 1 and 20; source_type and recency_window closed enums."
    },
    "retrieve_document": {
        "abuse_scenario": "An attacker uses path traversal ('../../etc/passwd' or 'file:///C:/...') to exfiltrate private operating system files or credentials.",
        "prevention_mechanism": "Strict regex pattern '^[A-Za-z0-9_-]+$' rejecting paths, slashes, and dots; dispatcher allow-list check against registered document index before disk access."
    },
    "calculate_metric": {
        "abuse_scenario": "An attacker uses arbitrary code execution / python eval injection ('__import__(\"os\").system(...)') via calculation expressions.",
        "prevention_mechanism": "Strict closed enum of deterministic mathematical operations ('growth_rate', 'cagr', etc.); values typed as array of floats; absolutely no eval() or exec() calls."
    },
    "compare_companies": {
        "abuse_scenario": "An attacker passes hundreds of arbitrary entity names or non-existent attributes to exhaust execution memory or induce synthetic hallucinations.",
        "prevention_mechanism": "Bounded array length (max 10 entities); attributes restricted to closed enum of 7 core corporate metrics; unestablished values marked explicitly as NOT_ESTABLISHED."
    },
    "save_research": {
        "abuse_scenario": "The model hallucinates a convincing statistic and invents a fictitious source reference to fabricate citations.",
        "prevention_mechanism": "Referential integrity check at dispatcher/handler: source_ref is validated against the active run's historical tool result IDs; untraceable records are rejected with an error."
    },
    "generate_report": {
        "abuse_scenario": "An unauthorized agent stage or rogue call attempts to prematurely emit or publish an incomplete report without human sign-off.",
        "prevention_mechanism": "Permission boundary check: write-class tool permitted only in designated synthesis/reporting stages; human approval gate is mandatory and cannot be triggered by tool."
    }
}

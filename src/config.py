"""
MarketMind AI - Configuration Management
Central, strongly-typed, validated configuration object.
Enforces startup validation, stage-specific model parameters, and budget caps.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Also load from system environment
    load_dotenv()


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class StageConfig:
    """Model and sampling settings for a specific pipeline stage."""
    model: str
    temperature: float
    max_tokens: Optional[int] = None


@dataclass
class RetryPolicy:
    """Settings governing network retry and backoff behavior."""
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 16.0
    timeout_seconds: float = 45.0


@dataclass
class BudgetConfig:
    """Hard boundaries governing agent execution."""
    max_research_questions: int = 15
    max_iterations: int = 15
    max_tool_calls: int = 30
    budget_ceiling_usd: float = 3.00
    max_repair_rounds: int = 2


@dataclass
class Settings:
    """Central application settings object."""
    # API Credentials & Connectivity
    openai_api_key: str
    openai_base_url: Optional[str] = None
    mock_mode: bool = False

    # Pipeline Stages Configuration
    stages: Dict[str, StageConfig] = field(default_factory=dict)

    # Execution Bounds & Budget
    budget: BudgetConfig = field(default_factory=BudgetConfig)

    # Resilience & Retries
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    # Storage Paths
    runs_dir: Path = field(default_factory=lambda: BASE_DIR / "runs")
    corpus_dir: Path = field(default_factory=lambda: BASE_DIR / "corpus")
    log_level: str = "INFO"

    def masked_api_key(self) -> str:
        """Return masked key for safe logging and display."""
        if not self.openai_api_key:
            return "[NOT SET]"
        if self.mock_mode:
            return "[MOCK_MODE_ACTIVE]"
        key = self.openai_api_key.strip()
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"


def load_settings() -> Settings:
    """
    Load, parse, and validate settings from environment variables.
    Fails loudly at startup if mandatory settings are missing.
    """
    mock_mode_str = os.getenv("MOCK_MODE", "false").lower()
    mock_mode = mock_mode_str in ("true", "1", "yes")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None

    # Startup validation: Fail loudly if API key is missing and not in mock mode
    if not mock_mode and not api_key:
        raise ConfigurationError(
            "CRITICAL CONFIGURATION ERROR: 'OPENAI_API_KEY' is missing or empty. "
            "Set OPENAI_API_KEY in your environment or .env file, or set MOCK_MODE=true for testing."
        )

    # Fallback placeholder in mock mode if key omitted
    if mock_mode and not api_key:
        api_key = "mock-key-marketmind-deterministic"

    # Per-stage model and temperature assignments with principled defaults
    stages: Dict[str, StageConfig] = {
        "request_analyser": StageConfig(
            model=os.getenv("REQUEST_ANALYSER_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("REQUEST_ANALYSER_TEMP", "0.0")),
        ),
        "planner": StageConfig(
            model=os.getenv("PLANNING_MODEL", "gpt-4o"),
            temperature=float(os.getenv("PLANNING_TEMP", "0.2")),
        ),
        "researcher": StageConfig(
            model=os.getenv("RESEARCHER_MODEL", "gpt-4o"),
            temperature=float(os.getenv("RESEARCHER_TEMP", "0.1")),
        ),
        "evidence_analyst": StageConfig(
            model=os.getenv("EVIDENCE_ANALYST_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("EVIDENCE_ANALYST_TEMP", "0.0")),
        ),
        "comparison": StageConfig(
            model=os.getenv("COMPARISON_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("COMPARISON_TEMP", "0.0")),
        ),
        "synthesis": StageConfig(
            model=os.getenv("SYNTHESIS_MODEL", "gpt-4o"),
            temperature=float(os.getenv("SYNTHESIS_TEMP", "0.3")),
        ),
        "quality_control": StageConfig(
            model=os.getenv("QC_MODEL", "gpt-4o"),
            temperature=float(os.getenv("QC_TEMP", "0.0")),
        ),
        "report_generator": StageConfig(
            model=os.getenv("REPORT_GENERATOR_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("REPORT_GENERATOR_TEMP", "0.0")),
        ),
    }

    budget = BudgetConfig(
        max_research_questions=int(os.getenv("MAX_RESEARCH_QUESTIONS", "15")),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "15")),
        max_tool_calls=int(os.getenv("MAX_TOOL_CALLS", "30")),
        budget_ceiling_usd=float(os.getenv("RUN_BUDGET_CEILING_USD", "3.00")),
        max_repair_rounds=int(os.getenv("MAX_REPAIR_ROUNDS", "2")),
    )

    retry = RetryPolicy(
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        initial_backoff_seconds=float(os.getenv("INITIAL_BACKOFF_SECONDS", "1.0")),
        max_backoff_seconds=float(os.getenv("MAX_BACKOFF_SECONDS", "16.0")),
        timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "45.0")),
    )

    runs_dir = Path(os.getenv("RUNS_DIR", str(BASE_DIR / "runs")))
    corpus_dir = Path(os.getenv("CORPUS_DIR", str(BASE_DIR / "corpus")))
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    return Settings(
        openai_api_key=api_key,
        openai_base_url=base_url,
        mock_mode=mock_mode,
        stages=stages,
        budget=budget,
        retry=retry,
        runs_dir=runs_dir,
        corpus_dir=corpus_dir,
        log_level=log_level,
    )


# Global settings singleton
try:
    settings = load_settings()
except ConfigurationError:
    # Allow import without crashing if environment is being set up or tested
    settings = None

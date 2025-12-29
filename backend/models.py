"""Pydantic models for the Deep Research Showcase API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ========================================
# Enums
# ========================================

class RunStatus(str, Enum):
    """Status of a research run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentPhase(str, Enum):
    """Current phase of the agent's ReAct loop."""
    PLANNING = "planning"
    INFORMATION_SEEKING = "information_seeking"
    REFLECTION = "reflection"
    CROSS_VALIDATION = "cross_validation"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"


class ToolType(str, Enum):
    """Types of tools available to the agent."""
    WEB_SEARCH = "web_search"
    WEB_BROWSE = "web_browse"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    TODO = "todo"
    SHELL = "shell"


class ClaimStatus(str, Enum):
    """Verification status of a claim."""
    SUPPORTED = "supported"
    REFUTED = "refuted"
    UNCERTAIN = "uncertain"
    UNVERIFIED = "unverified"


class AuthorityTier(str, Enum):
    """Authority tier for sources."""
    OFFICIAL = "official"
    ACADEMIC = "academic"
    INDUSTRY = "industry"
    MEDIA = "media"
    OTHER = "other"


class OutputFormat(str, Enum):
    """Output format for research reports."""
    REPORT = "report"
    ADR = "adr"
    BRIEF = "brief"
    MEMO = "memo"


class EngineType(str, Enum):
    """Type of research engine to use."""
    DEEP_RESEARCH = "deep_research"
    BASELINE = "baseline"


# ========================================
# Configuration Models
# ========================================

class AblationConfig(BaseModel):
    """Ablation toggle configuration."""
    enable_reflection: bool = Field(default=True, description="Enable reflection/cross-validation")
    enable_authority_ranking: bool = Field(default=True, description="Enable authority-aware ranking")
    enable_todo_state: bool = Field(default=True, description="Enable todo state tracking")
    enable_patch_editing: bool = Field(default=True, description="Enable patch-based editing")


class RunConfig(BaseModel):
    """Configuration for a research run."""
    engine: EngineType = Field(default=EngineType.DEEP_RESEARCH, description="Research engine")
    model_name: Optional[str] = Field(default=None, description="Model to use (overrides default)")
    model_base_url: Optional[str] = Field(default=None, description="Custom model base URL")
    output_format: OutputFormat = Field(default=OutputFormat.REPORT, description="Output format")
    max_steps: int = Field(default=50, ge=1, le=200, description="Maximum agent steps")
    verification_strictness: int = Field(
        default=2, ge=1, le=3,
        description="Verification strictness level (1=low, 2=medium, 3=high)"
    )
    time_horizon: Optional[str] = Field(default=None, description="Time horizon constraint")
    geography: Optional[str] = Field(default=None, description="Geographic constraint")
    required_sources: Optional[list[str]] = Field(default=None, description="Required source domains")
    ablations: AblationConfig = Field(default_factory=AblationConfig, description="Ablation config")


# ========================================
# Request Models
# ========================================

class CreateRunRequest(BaseModel):
    """Request to create a new research run."""
    query: str = Field(..., min_length=10, description="Research question")
    config: RunConfig = Field(default_factory=RunConfig, description="Run configuration")


class CreateTaskSetRequest(BaseModel):
    """Request to create a task set for evaluation."""
    name: str = Field(..., description="Task set name")
    description: Optional[str] = Field(default=None, description="Task set description")
    tasks: list[dict[str, Any]] = Field(..., description="List of tasks with query and format")


class PairwiseJudgmentRequest(BaseModel):
    """Request to record a pairwise comparison judgment."""
    run_a_id: str = Field(..., description="First run ID")
    run_b_id: str = Field(..., description="Second run ID")
    winner: str = Field(..., description="Winner: 'a', 'b', 'both_good', 'both_fair', 'both_poor'")
    completeness_a: int = Field(..., ge=1, le=5, description="Completeness score for A")
    completeness_b: int = Field(..., ge=1, le=5, description="Completeness score for B")
    depth_a: int = Field(..., ge=1, le=5, description="Depth score for A")
    depth_b: int = Field(..., ge=1, le=5, description="Depth score for B")
    readability_a: int = Field(..., ge=1, le=5, description="Readability score for A")
    readability_b: int = Field(..., ge=1, le=5, description="Readability score for B")
    requirement_fit_a: int = Field(..., ge=1, le=5, description="Requirement fit score for A")
    requirement_fit_b: int = Field(..., ge=1, le=5, description="Requirement fit score for B")
    notes: Optional[str] = Field(default=None, description="Evaluator notes")


# ========================================
# Tool Event Models
# ========================================

class ToolEvent(BaseModel):
    """A single tool invocation event."""
    event_id: str = Field(..., description="Unique event ID")
    run_id: str = Field(..., description="Parent run ID")
    tool: ToolType = Field(..., description="Tool type")
    tool_name: str = Field(..., description="Tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    result: Optional[Any] = Field(default=None, description="Tool result (inline or file ref)")
    result_file_path: Optional[str] = Field(default=None, description="Path to result file")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Start time")
    ended_at: Optional[datetime] = Field(default=None, description="End time")
    duration_ms: Optional[int] = Field(default=None, description="Duration in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ========================================
# Evidence and Citation Models
# ========================================

class Evidence(BaseModel):
    """Evidence item from web or file sources."""
    evidence_id: str = Field(..., description="Unique evidence ID")
    run_id: str = Field(..., description="Parent run ID")
    source_url: str = Field(..., description="Source URL")
    source_title: Optional[str] = Field(default=None, description="Source title")
    snippet: str = Field(..., description="Relevant text snippet")
    authority_tier: AuthorityTier = Field(
        default=AuthorityTier.OTHER,
        description="Authority tier"
    )
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Retrieval time")
    tool_event_id: Optional[str] = Field(default=None, description="Related tool event")
    cross_validated: bool = Field(default=False, description="Whether cross-validated")
    validation_sources: list[str] = Field(default_factory=list, description="Validation source IDs")


class Claim(BaseModel):
    """A factual claim extracted from the report."""
    claim_id: str = Field(..., description="Unique claim ID")
    run_id: str = Field(..., description="Parent run ID")
    text: str = Field(..., description="Claim text")
    status: ClaimStatus = Field(default=ClaimStatus.UNVERIFIED, description="Verification status")
    evidence_ids: list[str] = Field(default_factory=list, description="Supporting evidence IDs")
    section: Optional[str] = Field(default=None, description="Report section containing claim")
    confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Confidence score")


# ========================================
# Todo State Models
# ========================================

class TodoItem(BaseModel):
    """A single todo item for task tracking."""
    id: str = Field(..., description="Todo item ID")
    title: str = Field(..., description="Todo title")
    description: Optional[str] = Field(default=None, description="Todo description")
    status: str = Field(default="pending", description="Status: pending, in_progress, completed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    parent_id: Optional[str] = Field(default=None, description="Parent todo ID")


class TodoState(BaseModel):
    """Current state of the todo list."""
    items: list[TodoItem] = Field(default_factory=list, description="All todo items")
    completed_count: int = Field(default=0, description="Number of completed items")
    pending_count: int = Field(default=0, description="Number of pending items")


# ========================================
# Report Models
# ========================================

class ReportSection(BaseModel):
    """A section of the research report."""
    id: str = Field(..., description="Section ID")
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content in Markdown")
    claims: list[str] = Field(default_factory=list, description="Claim IDs in this section")
    order: int = Field(..., description="Section order")


class Report(BaseModel):
    """Complete research report."""
    run_id: str = Field(..., description="Parent run ID")
    title: str = Field(..., description="Report title")
    executive_summary: str = Field(default="", description="Executive summary")
    sections: list[ReportSection] = Field(default_factory=list, description="Report sections")
    markdown: str = Field(default="", description="Full report in Markdown")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    version: int = Field(default=1, description="Report version")


# ========================================
# Run Models
# ========================================

class RunMetrics(BaseModel):
    """Metrics collected during a research run."""
    total_tool_calls: int = Field(default=0, description="Total tool invocations")
    tool_calls_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Tool calls by type"
    )
    total_tokens: int = Field(default=0, description="Total tokens used")
    prompt_tokens: int = Field(default=0, description="Prompt tokens used")
    completion_tokens: int = Field(default=0, description="Completion tokens used")
    cost_estimate_usd: float = Field(default=0.0, description="Estimated cost in USD")
    latency_ms: int = Field(default=0, description="Total latency in milliseconds")
    reflection_steps: int = Field(default=0, description="Number of reflection steps")
    cross_validation_events: int = Field(default=0, description="Cross-validation events")
    citation_count: int = Field(default=0, description="Total citations")
    citation_authority_mix: dict[str, int] = Field(
        default_factory=dict,
        description="Citations by authority tier"
    )
    unsupported_claims: int = Field(default=0, description="Claims without citations")
    context_spill_to_disk_events: int = Field(default=0, description="Disk context spills")
    patch_edit_savings_percent: Optional[float] = Field(
        default=None,
        description="Token savings from patch editing"
    )


class Run(BaseModel):
    """A research run with all associated data."""
    run_id: str = Field(..., description="Unique run ID")
    query: str = Field(..., description="Original research question")
    config: RunConfig = Field(..., description="Run configuration")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Run status")
    current_phase: AgentPhase = Field(default=AgentPhase.PLANNING, description="Current phase")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    started_at: Optional[datetime] = Field(default=None, description="Start time")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    metrics: RunMetrics = Field(default_factory=RunMetrics, description="Run metrics")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    report_artifact_path: Optional[str] = Field(default=None, description="Path to report file")
    trace_path: Optional[str] = Field(default=None, description="Path to trace file")


class RunSummary(BaseModel):
    """Summary of a run for list views."""
    run_id: str
    query: str
    status: RunStatus
    engine: EngineType
    current_phase: AgentPhase
    created_at: datetime
    completed_at: Optional[datetime] = None
    citation_count: int = 0
    tool_calls: int = 0


# ========================================
# Comparison Models
# ========================================

class ClaimDiff(BaseModel):
    """Difference in claims between two runs."""
    claim_text: str
    status_a: Optional[ClaimStatus] = None
    status_b: Optional[ClaimStatus] = None
    evidence_count_a: int = 0
    evidence_count_b: int = 0
    in_both: bool = False


class RunComparison(BaseModel):
    """Comparison between two research runs."""
    run_a: RunSummary
    run_b: RunSummary
    report_diff_summary: str = Field(default="", description="Summary of report differences")
    claim_diffs: list[ClaimDiff] = Field(default_factory=list, description="Claim differences")
    metric_deltas: dict[str, Any] = Field(default_factory=dict, description="Metric differences")
    citation_comparison: dict[str, Any] = Field(
        default_factory=dict,
        description="Citation comparison"
    )


# ========================================
# WebSocket Event Models
# ========================================

class WSEventType(str, Enum):
    """WebSocket event types."""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    
    # Run lifecycle events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    # Agent phase events
    PHASE_CHANGED = "phase_changed"
    
    # Tool events
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    
    # Evidence events
    EVIDENCE_FOUND = "evidence_found"
    CLAIM_EXTRACTED = "claim_extracted"
    CLAIM_VERIFIED = "claim_verified"
    
    # Todo events
    TODO_UPDATED = "todo_updated"
    
    # Report events
    REPORT_DRAFT_UPDATED = "report_draft_updated"
    REPORT_SECTION_ADDED = "report_section_added"
    REPORT_FINALIZED = "report_finalized"
    
    # Metrics events
    METRICS_UPDATED = "metrics_updated"
    
    # Context events
    CONTEXT_SPILL = "context_spill"
    
    # Reflection events
    REFLECTION_STARTED = "reflection_started"
    CROSS_VALIDATION = "cross_validation"


class WSEvent(BaseModel):
    """WebSocket event message."""
    event_type: WSEventType = Field(..., description="Event type")
    run_id: str = Field(..., description="Run ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event time")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")


# ========================================
# Evaluation Models
# ========================================

class EvaluationTask(BaseModel):
    """A single evaluation task."""
    task_id: str
    query: str
    output_format: OutputFormat = OutputFormat.REPORT
    expected_criteria: Optional[list[str]] = None


class TaskSet(BaseModel):
    """A set of evaluation tasks."""
    task_set_id: str
    name: str
    description: Optional[str] = None
    tasks: list[EvaluationTask]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PairwiseResult(BaseModel):
    """Result of a pairwise evaluation."""
    result_id: str
    run_a_id: str
    run_b_id: str
    winner: str
    scores: dict[str, dict[str, int]]
    notes: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluator_id: Optional[str] = None


class EvaluationSummary(BaseModel):
    """Summary of evaluation results."""
    total_comparisons: int
    wins_by_engine: dict[str, int]
    average_scores: dict[str, dict[str, float]]
    elo_ratings: Optional[dict[str, float]] = None

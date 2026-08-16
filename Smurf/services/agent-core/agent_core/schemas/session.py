"""Session-related data models for Multi-Agent orchestration.

Follows docs/agent-core/03-contracts.md §3.1 (AgentEvent), §3.2 (EvidenceRecord).
All enums and schemas comply with Schema Intersection Rule.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    """State machine for AgentSession lifecycle."""
    CREATED = "CREATED"
    ROUTING = "ROUTING"
    DISPATCHING = "DISPATCHING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class AgentPhase(str, Enum):
    """Phase taxonomy for AgentEvent.phase (03-contracts.md §3.1)."""
    ROUTER = "ROUTER"
    COORDINATOR = "COORDINATOR"
    WORKER = "WORKER"
    ACTION = "ACTION"
    POLICY_GATE = "POLICY_GATE"
    TOOL = "TOOL"
    VERIFY = "VERIFY"
    NARRATIVE = "NARRATIVE"
    DONE = "DONE"


class AgentStatus(str, Enum):
    """Status for individual agent step."""
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class Playbook(str, Enum):
    """5 playbooks Router classifies requests into."""
    PLAN_IRRIGATION = "PLAN_IRRIGATION"
    INSPECT_SESSION = "INSPECT_SESSION"
    DEVICE_ISSUE = "DEVICE_ISSUE"
    REPORT = "REPORT"
    ASK_DATA = "ASK_DATA"


class Confidence(str, Enum):
    """Decision confidence level."""
    CONFIDENT = "CONFIDENT"
    TENTATIVE = "TENTATIVE"


class DataMode(str, Enum):
    """Data completeness mode."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"


@dataclass
class ToolCallMetadata:
    """Metadata for one tool invocation within an agent step."""
    tool: str
    arguments_summary: str
    ok: bool
    error_code: str
    duration_ms: int


@dataclass
class LLMCallMetadata:
    """Metadata proving an LLM was (or was not) invoked.

    Field `used: False` on deterministic steps (Policy Gate, Verifier)
    proves to UI which steps are code-only (ADR Rule 1).
    """
    used: bool
    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class AgentEvent:
    """One step in the agent trace (03-contracts.md §3.1).

    Published to topic_agent_events and streamed via SSE.
    """
    event_id: str
    session_id: str
    seq: int
    emitted_at_iso: str
    phase: AgentPhase
    agent: str
    status: AgentStatus
    title_vi: str
    detail_vi: str
    tool_calls: list[ToolCallMetadata] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    llm_call: LLMCallMetadata = field(default_factory=lambda: LLMCallMetadata(used=False))


@dataclass
class Decision:
    """One decision made during the session, with evidence trail."""
    decision_id: str
    statement_vi: str
    made_by_agent: str
    confidence: Confidence
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class Narrative:
    """Vietnamese narrative output from Narrative Agent.

    `text_vi` has every {EV-xxxx} placeholder already resolved to its actual
    value (ADR-003) — `evidence_table` is the audit trail behind it.
    """
    text_vi: str
    evidence_refs: list[str] = field(default_factory=list)
    key_tradeoffs: list[str] = field(default_factory=list)
    evidence_table: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentSession:
    """In-memory session state during orchestration.

    State machine: CREATED → ROUTING → DISPATCHING → ACTING → VERIFYING → COMPLETED/FAILED
    """
    session_id: str
    user_request: str
    requested_by: str
    created_at_iso: str

    state: SessionState = SessionState.CREATED
    playbook: Playbook | None = None

    # Accumulated during DISPATCHING rounds
    findings: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)

    # From ACTION phase
    action_plan: Any = None  # IrrigationSchedule | InspectionTicket | Notification | Report

    # From VERIFYING phase
    verification_result: Any = None  # VerificationResult

    # From NARRATIVE phase
    narrative: Narrative | None = None

    # Trace
    events: list[AgentEvent] = field(default_factory=list)
    event_seq_counter: int = 0

    # Metadata
    data_completeness: str = ""  # e.g. "5/6"
    mode: DataMode = DataMode.PARTIAL

    def add_event(self, event: AgentEvent) -> None:
        """Thread-safe event append with seq assignment."""
        event.seq = self.event_seq_counter
        self.event_seq_counter += 1
        self.events.append(event)


@dataclass
class SessionResult:
    """Full session output returned via GET /api/v1/agent/sessions/{id}.

    Combines AgentSession + evidence_ledger + timing.
    """
    session_id: str
    status: SessionState
    user_request: str
    playbook: Playbook | None
    mode: DataMode
    data_completeness: str

    narrative: Narrative | None
    decisions: list[Decision]
    evidence_ledger: list[dict[str, Any]]  # EvidenceRecord[] resolved from ledger
    actions: list[dict[str, Any]]  # IrrigationSchedule[] | InspectionTicket[] etc
    verification: dict[str, Any] | None  # VerificationResult
    agent_events: list[AgentEvent]

    timing: dict[str, Any]  # {total_ms, llm_calls, tool_calls}
    created_at_iso: str
    completed_at_iso: str = ""


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    """`AgentEvent` is a plain `@dataclass`, not a Pydantic `BaseModel` — no
    `.model_dump_json()`. This is the one place that turns it into a plain
    dict (enums resolved to their `.value`), reused by both the SSE stream
    (api/sessions.py) and the Kafka producer (orchestrator/coordinator.py)
    so there's a single source of truth for "what an AgentEvent looks like
    on the wire" instead of two divergent ad-hoc shapes."""
    return json.loads(json.dumps(asdict(event), default=_json_default, ensure_ascii=False))

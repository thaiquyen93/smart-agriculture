"""Data models for M2 Multi-Agent system.

Follows contracts in docs/agent-core/03-contracts.md.
All schemas comply with Schema Intersection Rule (no $ref, no anyOf, flat).
"""
from agent_core.schemas.session import (
    AgentEvent,
    AgentSession,
    Decision,
    LLMCallMetadata,
    Narrative,
    SessionResult,
    SessionState,
    ToolCallMetadata,
)
from agent_core.schemas.action import (
    ActionPlan,
    ActionType,
    InspectionTicket,
    IrrigationSchedule,
    Notification,
    Report,
)
from agent_core.schemas.verification import (
    EvidenceAudit,
    FieldDifference,
    VerificationResult,
    VerificationStatus,
)
from agent_core.schemas.policy import (
    PolicyResult,
    PolicyViolation,
    PolicyRuleCode,
)

__all__ = [
    # Session
    "AgentEvent",
    "AgentSession",
    "Decision",
    "LLMCallMetadata",
    "Narrative",
    "SessionResult",
    "SessionState",
    "ToolCallMetadata",
    # Action
    "ActionPlan",
    "ActionType",
    "InspectionTicket",
    "IrrigationSchedule",
    "Notification",
    "Report",
    # Verification
    "EvidenceAudit",
    "FieldDifference",
    "VerificationResult",
    "VerificationStatus",
    # Policy
    "PolicyResult",
    "PolicyViolation",
    "PolicyRuleCode",
]

"""Policy Gate data models.

Policy Gate is deterministic code, not LLM (ADR Rule 1).
Enforces hard constraints before action execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PolicyRuleCode(str, Enum):
    """Policy rule identifiers (for traceability)."""
    MIN_TANK_LEVEL = "MIN_TANK_LEVEL"
    APPROVAL_THRESHOLD_LITERS = "APPROVAL_THRESHOLD_LITERS"
    MAX_VOLUME_LITERS = "MAX_VOLUME_LITERS"
    MAX_DURATION_MINUTES = "MAX_DURATION_MINUTES"
    PUMP_STATUS_OK = "PUMP_STATUS_OK"
    EVIDENCE_FRESHNESS = "EVIDENCE_FRESHNESS"


@dataclass
class PolicyViolation:
    """One policy constraint violation."""
    rule_code: PolicyRuleCode
    message_vi: str
    current_value: str
    threshold: str


@dataclass
class PolicyResult:
    """Result from PolicyGate.validate().

    passed=False → session fails immediately.
    approval_required=True → action status becomes PENDING_APPROVAL.
    """
    passed: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    approval_required: bool = False
    approval_reason_vi: str = ""
    modified_plan: dict | None = None  # Policy Gate can clamp values (e.g. max volume)

"""Action plan data models (irrigation, inspection, notification, report).

Follows docs/agent-core/03-contracts.md §3.3, §3.4, §3.5.
All schemas comply with Schema Intersection Rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    """Type discriminator for action plans."""
    IRRIGATION_SCHEDULE = "IRRIGATION_SCHEDULE"
    INSPECTION_TICKET = "INSPECTION_TICKET"
    NOTIFICATION = "NOTIFICATION"
    REPORT = "REPORT"


class ScheduleStatus(str, Enum):
    """Status for IrrigationSchedule (03-contracts.md §3.3)."""
    SCHEDULED = "SCHEDULED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"


class Priority(str, Enum):
    """Priority level for plans and tickets."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Confidence(str, Enum):
    """Confidence level for decisions."""
    CONFIDENT = "CONFIDENT"
    TENTATIVE = "TENTATIVE"


class DataMode(str, Enum):
    """Data completeness mode."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class TicketStatus(str, Enum):
    """Status for InspectionTicket (03-contracts.md §3.4)."""
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class IssueType(str, Enum):
    """Issue types for inspection tickets."""
    SENSOR_OFFLINE = "SENSOR_OFFLINE"
    SENSOR_DRIFT = "SENSOR_DRIFT"
    PUMP_FAULT = "PUMP_FAULT"
    LOW_TANK = "LOW_TANK"
    PH_OUT_OF_RANGE = "PH_OUT_OF_RANGE"
    OTHER = "OTHER"


class NotificationAudience(str, Enum):
    """Target audience for notifications."""
    MANAGER = "MANAGER"
    FIELD_TEAM = "FIELD_TEAM"
    AGRONOMIST = "AGRONOMIST"


class NotificationSeverity(str, Enum):
    """Severity level for notifications."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RelatedObjectType(str, Enum):
    """Type of related object in notifications."""
    IRRIGATION_SCHEDULE = "IRRIGATION_SCHEDULE"
    INSPECTION_TICKET = "INSPECTION_TICKET"
    REPORT = "REPORT"
    NONE = "NONE"


@dataclass
class IrrigationSchedule:
    """Irrigation plan created by Action Agent (03-contracts.md §3.3)."""
    schedule_id: str
    session_id: str
    zone: str
    start_time_iso: str
    duration_minutes: int
    target_volume_liters: float
    priority: Priority
    status: ScheduleStatus
    reason_vi: str
    confidence: Confidence
    data_completeness: str
    mode: DataMode
    evidence_refs: list[str] = field(default_factory=list)
    created_by_agent: str = "FarmActionAgent"
    approval_id: str = ""
    created_at_iso: str = ""


@dataclass
class InspectionTicket:
    """Inspection ticket for field team (03-contracts.md §3.4)."""
    ticket_id: str
    session_id: str
    device_id: str
    issue_type: IssueType
    priority: Priority
    status: TicketStatus
    description_vi: str
    assignee_staff_id: str
    assignee_name: str
    evidence_refs: list[str] = field(default_factory=list)
    created_by_agent: str = "FarmActionAgent"
    created_at_iso: str = ""


@dataclass
class Notification:
    """Notification message (03-contracts.md §3.5)."""
    notification_id: str
    session_id: str
    audience: NotificationAudience
    severity: NotificationSeverity
    title_vi: str
    body_vi: str
    evidence_refs: list[str] = field(default_factory=list)
    related_object_type: RelatedObjectType = RelatedObjectType.NONE
    related_object_id: str = ""
    created_at_iso: str = ""


@dataclass
class Report:
    """Generated report (ad-hoc summary)."""
    report_id: str
    session_id: str
    report_type: str  # "DAILY_SUMMARY" | "IRRIGATION_HISTORY" | "DEVICE_STATUS"
    title_vi: str
    content_vi: str
    evidence_refs: list[str] = field(default_factory=list)
    generated_at_iso: str = ""


@dataclass
class ActionPlan:
    """Discriminated union wrapper for action plans.

    Used internally during orchestration before casting to specific type.
    """
    action_type: ActionType
    payload: IrrigationSchedule | InspectionTicket | Notification | Report

"""Action Agent tools (create irrigation schedule, inspection ticket, notification, report).

Follows docs/agent-core/02-agents-and-tools.md §C.5.
These are WRITE tools — idempotent via idempotency_key, return stable IDs.
"""
from __future__ import annotations

import time
from datetime import datetime

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.schemas.action import (
    Confidence,
    DataMode,
    InspectionTicket,
    IrrigationSchedule,
    IssueType,
    Notification,
    NotificationAudience,
    NotificationSeverity,
    Priority,
    RelatedObjectType,
    Report,
    ScheduleStatus,
    TicketStatus,
)
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso


# In-memory idempotency cache (M2 scope: single-instance)
_idempotency_cache: dict[str, str] = {}


def _error(code: str, message: str, *, retryable: bool = False, suggested_action: str = "NONE") -> dict:
    return {
        "ok": False,
        "error_code": code,
        "message": message,
        "retryable": retryable,
        "suggested_action": suggested_action,
    }


def _generate_id(prefix: str) -> str:
    """Generate stable ID: PREFIX-YYYYMMDD-NNNN."""
    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    seq = int(now.timestamp() * 1000) % 10000  # Last 4 digits of ms timestamp
    return f"{prefix}-{date_part}-{seq:04d}"


def create_irrigation_schedule(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    session_id: str,
    zone: str,
    start_time_iso: str,
    duration_minutes: int,
    target_volume_liters: float,
    priority: str,
    reason_vi: str,
    confidence: str,
    data_completeness: str,
    mode: str,
    evidence_refs: list[str],
    idempotency_key: str,
) -> dict:
    """Create irrigation schedule.

    Returns: {ok, schedule_id, schedule, markdown}
    """
    # Idempotency check
    if idempotency_key in _idempotency_cache:
        existing_id = _idempotency_cache[idempotency_key]
        return {
            "ok": True,
            "schedule_id": existing_id,
            "schedule": None,  # Would fetch from DB in production
            "markdown": f"✅ Lịch tưới **{existing_id}** (idempotent, đã tồn tại).",
        }

    schedule_id = _generate_id("PLAN")
    _idempotency_cache[idempotency_key] = schedule_id

    schedule = IrrigationSchedule(
        schedule_id=schedule_id,
        session_id=session_id,
        zone=zone,
        start_time_iso=start_time_iso,
        duration_minutes=duration_minutes,
        target_volume_liters=target_volume_liters,
        priority=Priority(priority),
        status=ScheduleStatus.SCHEDULED,  # Will be updated by Policy Gate
        reason_vi=reason_vi,
        confidence=Confidence(confidence),
        data_completeness=data_completeness,
        mode=DataMode(mode),
        evidence_refs=evidence_refs,
        created_by_agent="FarmActionAgent",
        created_at_iso=to_iso(time.time()),
    )

    # M2: in-memory only. M3: persist to SQLite/PostgreSQL
    markdown = (
        f"✅ Tạo lịch tưới **{schedule_id}**: {target_volume_liters:.0f} L, "
        f"{duration_minutes} phút, bắt đầu {start_time_iso}."
    )

    return {
        "ok": True,
        "schedule_id": schedule_id,
        "schedule": schedule,
        "markdown": markdown,
    }


def create_inspection_ticket(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    session_id: str,
    device_id: str,
    issue_type: str,
    priority: str,
    description_vi: str,
    assignee_staff_id: str,
    assignee_name: str,
    evidence_refs: list[str],
    idempotency_key: str,
) -> dict:
    """Create inspection ticket for field team.

    Returns: {ok, ticket_id, ticket, markdown}
    """
    if idempotency_key in _idempotency_cache:
        existing_id = _idempotency_cache[idempotency_key]
        return {
            "ok": True,
            "ticket_id": existing_id,
            "ticket": None,
            "markdown": f"✅ Phiếu kiểm tra **{existing_id}** (idempotent, đã tồn tại).",
        }

    ticket_id = _generate_id("TASK")
    _idempotency_cache[idempotency_key] = ticket_id

    ticket = InspectionTicket(
        ticket_id=ticket_id,
        session_id=session_id,
        device_id=device_id,
        issue_type=IssueType(issue_type),
        priority=Priority(priority),
        status=TicketStatus.OPEN,
        description_vi=description_vi,
        assignee_staff_id=assignee_staff_id,
        assignee_name=assignee_name,
        evidence_refs=evidence_refs,
        created_by_agent="FarmActionAgent",
        created_at_iso=to_iso(time.time()),
    )

    markdown = f"✅ Tạo phiếu kiểm tra **{ticket_id}**: {device_id} - {issue_type}. Giao cho {assignee_name}."

    return {
        "ok": True,
        "ticket_id": ticket_id,
        "ticket": ticket,
        "markdown": markdown,
    }


def send_notification(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    session_id: str,
    audience: str,
    severity: str,
    title_vi: str,
    body_vi: str,
    evidence_refs: list[str],
    related_object_type: str = "NONE",
    related_object_id: str = "",
    idempotency_key: str,
) -> dict:
    """Send notification to target audience.

    Returns: {ok, notification_id, notification, markdown}
    """
    if idempotency_key in _idempotency_cache:
        existing_id = _idempotency_cache[idempotency_key]
        return {
            "ok": True,
            "notification_id": existing_id,
            "notification": None,
            "markdown": f"✅ Thông báo **{existing_id}** (idempotent, đã gửi).",
        }

    notification_id = _generate_id("NTF")
    _idempotency_cache[idempotency_key] = notification_id

    notification = Notification(
        notification_id=notification_id,
        session_id=session_id,
        audience=NotificationAudience(audience),
        severity=NotificationSeverity(severity),
        title_vi=title_vi,
        body_vi=body_vi,
        evidence_refs=evidence_refs,
        related_object_type=RelatedObjectType(related_object_type),
        related_object_id=related_object_id,
        created_at_iso=to_iso(time.time()),
    )

    markdown = f"✅ Gửi thông báo **{notification_id}** tới {audience}: {title_vi}."

    return {
        "ok": True,
        "notification_id": notification_id,
        "notification": notification,
        "markdown": markdown,
    }


def generate_report(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    session_id: str,
    report_type: str,
    title_vi: str,
    content_vi: str,
    evidence_refs: list[str],
    idempotency_key: str,
) -> dict:
    """Generate ad-hoc report.

    Returns: {ok, report_id, report, markdown}
    """
    if idempotency_key in _idempotency_cache:
        existing_id = _idempotency_cache[idempotency_key]
        return {
            "ok": True,
            "report_id": existing_id,
            "report": None,
            "markdown": f"✅ Báo cáo **{existing_id}** (idempotent, đã tồn tại).",
        }

    report_id = _generate_id("RPT")
    _idempotency_cache[idempotency_key] = report_id

    report = Report(
        report_id=report_id,
        session_id=session_id,
        report_type=report_type,
        title_vi=title_vi,
        content_vi=content_vi,
        evidence_refs=evidence_refs,
        generated_at_iso=to_iso(time.time()),
    )

    markdown = f"✅ Tạo báo cáo **{report_id}**: {title_vi}."

    return {
        "ok": True,
        "report_id": report_id,
        "report": report,
        "markdown": markdown,
    }

"""API routes for irrigation plans.

GET /api/v1/plans — list all plans
GET /api/v1/plans/{id} — get plan details
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.tools import action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["plans"])


class PlanResponse(BaseModel):
    """Response for GET /api/v1/plans/{id}."""

    schedule_id: str
    zone: str
    start_time_iso: str
    duration_minutes: int
    target_volume_liters: float
    priority: str
    status: str
    reason_vi: str
    confidence: str


@router.get("/plans")
async def list_plans():
    """List all irrigation plans (from the in-memory plan store in M2).

    M3: Query from DB.
    """
    plans = [_to_response(schedule).model_dump() for schedule in action.list_irrigation_schedules()]

    return {
        "plans": plans,
        "total": len(plans),
    }


@router.get("/plans/{schedule_id}")
async def get_plan(schedule_id: str):
    """Get irrigation plan details.

    M2: real read from the in-memory plan store (agent_core.tools.action).
    M3: Query from DB.
    """
    schedule = action.get_irrigation_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    return _to_response(schedule)


def _to_response(schedule) -> PlanResponse:
    return PlanResponse(
        schedule_id=schedule.schedule_id,
        zone=schedule.zone,
        start_time_iso=schedule.start_time_iso,
        duration_minutes=schedule.duration_minutes,
        target_volume_liters=schedule.target_volume_liters,
        priority=schedule.priority.value,
        status=schedule.status.value,
        reason_vi=schedule.reason_vi,
        confidence=schedule.confidence.value,
    )

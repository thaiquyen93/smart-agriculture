"""API routes for irrigation plans.

GET /api/v1/plans — list all plans
GET /api/v1/plans/{id} — get plan details
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.tools.action import _idempotency_cache

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
    """List all irrigation plans (from idempotency cache in M2).

    M3: Query from DB.
    """
    # M2: in-memory cache
    plans = []
    for schedule_id in _idempotency_cache.values():
        plans.append({"schedule_id": schedule_id})

    return {
        "plans": plans,
        "total": len(plans),
    }


@router.get("/plans/{schedule_id}")
async def get_plan(schedule_id: str):
    """Get irrigation plan details.

    M2: Mock response (idempotency cache only stores IDs).
    M3: Query from DB.
    """
    # Check if plan exists in cache
    if schedule_id not in _idempotency_cache.values():
        raise HTTPException(status_code=404, detail="Plan not found")

    # M2: Return mock plan
    return PlanResponse(
        schedule_id=schedule_id,
        zone="ZONE_A",
        start_time_iso="2026-08-16T16:30:00+07:00",
        duration_minutes=28,
        target_volume_liters=412.0,
        priority="HIGH",
        status="SCHEDULED",
        reason_vi="Độ ẩm đất thấp, cần bù nước theo ET0",
        confidence="CONFIDENT",
    )

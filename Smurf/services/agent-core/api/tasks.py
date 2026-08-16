"""API routes for inspection tasks/tickets.

GET /api/v1/tasks — list all tasks
GET /api/v1/tasks/{id} — get task details
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["tasks"])


class TaskResponse(BaseModel):
    """Response for GET /api/v1/tasks/{id}."""

    ticket_id: str
    zone: str
    issue_type: str
    description_vi: str
    priority: str
    status: str


# M2: In-memory task store (mock)
_tasks: dict[str, dict] = {}


@router.get("/tasks")
async def list_tasks():
    """List all inspection tasks.

    M2: In-memory store.
    M3: Query from DB.
    """
    return {
        "tasks": list(_tasks.values()),
        "total": len(_tasks),
    }


@router.get("/tasks/{ticket_id}")
async def get_task(ticket_id: str):
    """Get inspection task details."""
    task = _tasks.get(ticket_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(**task)

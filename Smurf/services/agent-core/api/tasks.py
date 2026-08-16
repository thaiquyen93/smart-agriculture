"""API routes for inspection tasks/tickets.

GET /api/v1/tasks — list all tasks
GET /api/v1/tasks/{id} — get task details
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.tools import action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["tasks"])


class TaskResponse(BaseModel):
    """Response for GET /api/v1/tasks/{id}."""

    ticket_id: str
    device_id: str
    issue_type: str
    description_vi: str
    priority: str
    status: str


@router.get("/tasks")
async def list_tasks():
    """List all inspection tasks (from the in-memory ticket store in M2).

    M3: Query from DB.
    """
    tasks = [_to_response(ticket).model_dump() for ticket in action.list_inspection_tickets()]

    return {
        "tasks": tasks,
        "total": len(tasks),
    }


@router.get("/tasks/{ticket_id}")
async def get_task(ticket_id: str):
    """Get inspection task details.

    M2: real read from the in-memory ticket store (agent_core.tools.action).
    M3: Query from DB.
    """
    ticket = action.get_inspection_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return _to_response(ticket)


def _to_response(ticket) -> TaskResponse:
    return TaskResponse(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        issue_type=ticket.issue_type.value,
        description_vi=ticket.description_vi,
        priority=ticket.priority.value,
        status=ticket.status.value,
    )

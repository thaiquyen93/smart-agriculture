"""API routes for agent sessions.

POST /api/v1/agent/sessions — create new session (202 Accepted)
GET /api/v1/sessions/{id} — get session state
GET /api/v1/sessions/{id}/stream — SSE live trace
POST /api/v1/approvals/{id} — approve/reject pending plans
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_core.orchestrator import Orchestrator, SessionManager
from agent_core.schemas.session import SessionState, event_to_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request body for POST /api/v1/agent/sessions."""

    user_request: str
    user_id: Optional[str] = None
    metadata: Optional[dict] = None


class SessionResponse(BaseModel):
    """Response for GET /api/v1/sessions/{id}."""

    session_id: str
    state: str
    user_request: str
    playbook: Optional[str] = None
    action_plan_id: Optional[str] = None
    verification_verdict: Optional[str] = None
    narrative_text: Optional[str] = None
    events_count: int


class ApprovalRequest(BaseModel):
    """Request body for POST /api/v1/approvals/{id}."""

    approved: bool
    reason: Optional[str] = None


# Global orchestrator instance (injected by main.py)
_orchestrator: Orchestrator | None = None


def set_orchestrator(orchestrator: Orchestrator):
    """Inject orchestrator dependency."""
    global _orchestrator
    _orchestrator = orchestrator


@router.post("/agent/sessions", status_code=202)
async def create_session(request: CreateSessionRequest, background_tasks: BackgroundTasks):
    """Create new agent session and run in background.

    Returns 202 Accepted immediately.
    """
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    # Create session
    session = SessionManager.create(request.user_request, requested_by=request.user_id or "unknown")

    # Spawn background task
    background_tasks.add_task(_run_session_background, session.session_id)

    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "message": "Session created. Processing in background.",
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state snapshot."""
    session = SessionManager.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.session_id,
        state=session.state.value,
        user_request=session.user_request,
        playbook=session.playbook.value if session.playbook else None,
        action_plan_id=session.action_plan.schedule_id if session.action_plan else None,
        verification_verdict=session.verification_result.verdict.value if session.verification_result else None,
        narrative_text=session.narrative.text_vi if session.narrative else None,
        events_count=len(session.events),
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str, request: Request):
    """Stream session events as SSE (Server-Sent Events).

    Client receives real-time agent_event updates.
    """
    session = SessionManager.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        """Generate SSE events."""
        last_event_count = 0

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE stream: %s", session_id)
                break

            # Get fresh session
            current_session = SessionManager.get(session_id)
            if not current_session:
                break

            # Send new events
            if len(current_session.events) > last_event_count:
                for event in current_session.events[last_event_count:]:
                    yield f"event: agent_event\n"
                    yield f"data: {json.dumps(event_to_dict(event), ensure_ascii=False)}\n\n"

                last_event_count = len(current_session.events)

            # Check if session completed
            if current_session.state in [SessionState.COMPLETED, SessionState.FAILED]:
                yield f"event: session_complete\n"
                yield f"data: {json.dumps({'state': current_session.state.value})}\n\n"
                break

            # Wait before next poll
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/approvals/{session_id}")
async def approve_session(session_id: str, request: ApprovalRequest, background_tasks: BackgroundTasks):
    """Approve or reject a pending action plan."""
    session = SessionManager.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.state != SessionState.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Session not awaiting approval (state: {session.state.value})")

    if request.approved:
        # Resume session (continue to VERIFYING)
        background_tasks.add_task(_resume_session_after_approval, session_id)
        return {"message": "Approved. Resuming session."}
    else:
        # Reject
        session.state = SessionState.FAILED
        SessionManager.update(session)
        return {"message": "Rejected. Session terminated."}


@router.get("/sessions")
async def list_sessions():
    """List all sessions (for debugging)."""
    sessions = SessionManager.list_all()
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "state": s.state.value,
                "user_request": s.user_request[:50] + "..." if len(s.user_request) > 50 else s.user_request,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


async def _run_session_background(session_id: str):
    """Background task to run session in a worker thread (non-blocking for FastAPI event loop)."""
    try:
        session = SessionManager.get(session_id)
        if not session:
            logger.error("Session %s not found for background run", session_id)
            return

        logger.info("Starting background session: %s", session_id)

        # Run orchestrator in worker thread so FastAPI event loop stays responsive
        updated_session = await asyncio.to_thread(_orchestrator.run_session, session)

        # Save updated session
        SessionManager.update(updated_session)

        logger.info("Session %s completed with state: %s", session_id, updated_session.state.value)

    except Exception as exc:
        logger.error("Background session %s failed: %s", session_id, exc, exc_info=True)
        session = SessionManager.get(session_id)
        if session:
            session.state = SessionState.FAILED
            SessionManager.update(session)


async def _resume_session_after_approval(session_id: str):
    """Resume session after human approval."""
    try:
        session = SessionManager.get(session_id)
        if not session:
            return

        # Continue from VERIFYING
        session.state = SessionState.ACTING  # Will transition to VERIFYING in orchestrator

        # Run remaining phases in worker thread
        updated_session = await asyncio.to_thread(_orchestrator._verify, session)
        if updated_session.state != SessionState.FAILED:
            updated_session = await asyncio.to_thread(_orchestrator._narrate, updated_session)
            updated_session.state = SessionState.COMPLETED

        SessionManager.update(updated_session)

    except Exception as exc:
        logger.error("Resume session %s failed: %s", session_id, exc, exc_info=True)

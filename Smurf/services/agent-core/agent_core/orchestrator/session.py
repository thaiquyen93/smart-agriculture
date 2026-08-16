"""Session management — in-memory session store and state machine.

M2: In-memory dict (singleton SessionManager).
M3: Move to DB persistence for multi-instance + resume.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from agent_core.schemas.session import AgentSession, SessionState

# In-memory session store (singleton)
_sessions: dict[str, AgentSession] = {}
_sessions_lock = threading.Lock()


def _generate_session_id() -> str:
    """Generate session ID: SESSION-YYYYMMDD-NNNN."""
    from datetime import datetime

    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    seq = int(now.timestamp() * 1000) % 10000
    return f"SESSION-{date_part}-{seq:04d}"


class SessionManager:
    """Manages agent sessions (in-memory for M2)."""

    @staticmethod
    def create(user_request: str) -> AgentSession:
        """Create new session."""
        session_id = _generate_session_id()
        session = AgentSession(
            session_id=session_id,
            user_request=user_request,
            state=SessionState.CREATED,
        )

        with _sessions_lock:
            _sessions[session_id] = session

        return session

    @staticmethod
    def get(session_id: str) -> AgentSession | None:
        """Get session by ID."""
        with _sessions_lock:
            return _sessions.get(session_id)

    @staticmethod
    def update(session: AgentSession) -> None:
        """Update session state."""
        with _sessions_lock:
            _sessions[session.session_id] = session

    @staticmethod
    def delete(session_id: str) -> None:
        """Delete session."""
        with _sessions_lock:
            _sessions.pop(session_id, None)

    @staticmethod
    def list_all() -> list[AgentSession]:
        """List all sessions."""
        with _sessions_lock:
            return list(_sessions.values())

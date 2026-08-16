import re

file_path = 'd:/smurf_su2026/Smurf/services/agent-core/agent_core/orchestrator/coordinator.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# Add imports
if 'AgentPhase' not in content:
    content = content.replace('AgentSession, SessionState', 'AgentSession, SessionState, AgentPhase, AgentStatus, LLMCallMetadata')
if 'import uuid' not in content:
    content = 'import uuid\n' + content

# Add helper method
helper = '''
    def _create_event(self, session, phase: AgentPhase, agent: str, title_vi: str, detail_vi: str, llm_call: dict = None):
        if llm_call:
            llm_metadata = LLMCallMetadata(
                used=True,
                model=llm_call.get('model', ''),
                provider=llm_call.get('provider', ''),
                duration_ms=llm_call.get('duration_ms', 0),
                prompt_tokens=llm_call.get('prompt_tokens', 0),
                completion_tokens=llm_call.get('completion_tokens', 0),
            )
        else:
            llm_metadata = LLMCallMetadata(used=False)

        from agent_core.schemas.session import AgentEvent
        from agent_core.timeutil import to_iso
        import time
        return AgentEvent(
            event_id=uuid.uuid4().hex[:8],
            session_id=session.session_id,
            seq=len(session.events),
            emitted_at_iso=to_iso(time.time()),
            phase=phase,
            agent=agent,
            status=AgentStatus.SUCCEEDED,
            title_vi=title_vi,
            detail_vi=detail_vi,
            llm_call=llm_metadata
        )
'''
if '_create_event' not in content:
    content = content.replace('    def run_session(self, session: AgentSession) -> AgentSession:', helper + '\n    def run_session(self, session: AgentSession) -> AgentSession:')

# Replacements using exact string matches
reps = [
    (
'''        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Router",
            phase="ROUTING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=f"Playbook: {router_result['playbook'].value}, Zone: {router_result['zone']}",
            llm_call=router_result["llm_call_metadata"],
            duration_ms=router_result["duration_ms"],
        )''',
'''        event = self._create_event(session, AgentPhase.ROUTER, "Router", "Phân loại yêu cầu", f"Playbook: {router_result['playbook'].value}, Zone: {router_result['zone']}", router_result.get("llm_call_metadata"))'''
    ),
    (
'''                event = AgentEvent(
                    session_id=session.session_id,
                    agent_name=agent_name,
                    phase="DISPATCHING",
                    sequence=len(session.events),
                    timestamp_iso=to_iso(time.time()),
                    status="COMPLETED",
                    result_summary=result.get("recommendation", ""),
                    llm_call=result.get("llm_call_metadata"),
                    duration_ms=result.get("duration_ms", 0),
                )''',
'''                event = self._create_event(session, AgentPhase.WORKER, agent_name, "Nhiệm vụ Worker", result.get("recommendation", ""), result.get("llm_call_metadata"))'''
    ),
    (
'''            event = AgentEvent(
                session_id=session.session_id,
                agent_name="Coordinator",
                phase="DISPATCHING",
                sequence=len(session.events),
                timestamp_iso=to_iso(time.time()),
                status="COMPLETED",
                result_summary=coordinator_result["reasoning"],
                llm_call=coordinator_result["llm_call_metadata"],
                duration_ms=coordinator_result["duration_ms"],
            )''',
'''            event = self._create_event(session, AgentPhase.COORDINATOR, "Coordinator", "Tổng hợp Worker", coordinator_result["reasoning"], coordinator_result.get("llm_call_metadata"))'''
    ),
    (
'''        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Action",
            phase="ACTING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=f"Lên kế hoạch: {len(action_result['actions'])} hành động",
            llm_call=action_result["llm_call_metadata"],
            duration_ms=action_result["duration_ms"],
        )''',
'''        event = self._create_event(session, AgentPhase.ACTION, "Action", "Lên kế hoạch", f"Lên kế hoạch: {len(action_result['actions'])} hành động", action_result.get("llm_call_metadata"))'''
    ),
    (
'''        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Verifier",
            phase="VERIFYING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=verifier_result["summary_vi"],
        )''',
'''        event = self._create_event(session, AgentPhase.VERIFY, "Verifier", "Kiểm tra an toàn", verifier_result["summary_vi"])'''
    ),
    (
'''        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Narrative",
            phase="NARRATIVE",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary="Generated final response",
            llm_call=narrative_result["llm_call_metadata"],
            duration_ms=narrative_result["duration_ms"],
        )''',
'''        event = self._create_event(session, AgentPhase.NARRATIVE, "Narrative", "Tạo phản hồi", "Generated final response", narrative_result.get("llm_call_metadata"))'''
    )
]

for old, new in reps:
    if old in content:
        content = content.replace(old, new)
        print('Replaced')
    else:
        print('Not found')

if content != original_content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')

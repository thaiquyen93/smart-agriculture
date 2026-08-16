"""Orchestrator — main run_session() state machine with parallel worker dispatch.

Follows Implementation Plan orchestration flow.
State transitions: CREATED → ROUTING → DISPATCHING → ACTING → VERIFYING → COMPLETED/FAILED
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_core.agents import (
    ActionAgent,
    AgronomyAgent,
    CoordinatorAgent,
    FieldIoTAgent,
    NarrativeAgent,
    ResourceAgent,
    RouterAgent,
)
from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.kafka.producer import AgentEventProducer
from agent_core.policy.gate import PolicyGate
from agent_core.schemas.session import AgentEvent, AgentSession, SessionState
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso
from agent_core.verifier.verifier import Verifier

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestrator — runs session state machine with parallel dispatch."""

    def __init__(
        self,
        store: FarmStateStore,
        ledger: EvidenceLedger,
        settings: Settings,
        kafka_producer: AgentEventProducer,
    ):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.kafka_producer = kafka_producer

        # Initialize agents
        self.router = RouterAgent(store, ledger, settings)
        self.coordinator = CoordinatorAgent(store, ledger, settings)
        self.field_iot = FieldIoTAgent(store, ledger, settings)
        self.agronomy = AgronomyAgent(store, ledger, settings)
        self.resource = ResourceAgent(store, ledger, settings)
        self.action = ActionAgent(store, ledger, settings)
        self.narrative = NarrativeAgent(store, ledger, settings)
        self.policy_gate = PolicyGate(store, ledger, settings)
        self.verifier = Verifier(store, ledger, settings)

    def run_session(self, session: AgentSession) -> AgentSession:
        """Run complete session through state machine.

        State flow:
        CREATED → ROUTING → DISPATCHING → ACTING → VERIFYING → COMPLETED/FAILED
        """
        try:
            # 1. ROUTING
            session = self._route(session)
            if session.state == SessionState.FAILED:
                return session

            # 2. DISPATCHING (max 2 rounds)
            session = self._dispatch(session)
            if session.state == SessionState.FAILED:
                return session

            # 3. ACTING
            session = self._act(session)
            if session.state in [SessionState.FAILED, SessionState.AWAITING_APPROVAL]:
                return session

            # 4. VERIFYING
            session = self._verify(session)
            if session.state == SessionState.FAILED:
                return session

            # 5. NARRATIVE
            session = self._narrate(session)

            session.state = SessionState.COMPLETED
            return session

        except Exception as exc:
            logger.error("Orchestrator run_session failed: %s", exc, exc_info=True)
            session.state = SessionState.FAILED
            self._emit_event(session, "orchestrator", {"error": str(exc)})
            return session

    def _route(self, session: AgentSession) -> AgentSession:
        """Phase 1: ROUTING — classify user request into playbook."""
        session.state = SessionState.ROUTING
        logger.info("Session %s: ROUTING", session.session_id)

        router_result = self.router.execute(session.user_request)

        session.playbook = router_result["playbook"]

        # Emit event
        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Router",
            phase="ROUTING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=f"Playbook: {router_result['playbook'].value}, Zone: {router_result['zone']}",
            llm_call=router_result["llm_call_metadata"],
            duration_ms=router_result["duration_ms"],
        )
        session.events.append(event)
        self._emit_event(session, "Router", router_result)

        return session

    def _dispatch(self, session: AgentSession) -> AgentSession:
        """Phase 2: DISPATCHING — parallel worker dispatch (max 2 rounds)."""
        session.state = SessionState.DISPATCHING
        logger.info("Session %s: DISPATCHING", session.session_id)

        max_rounds = self.settings.agent_max_dispatch_rounds

        for round_num in range(1, max_rounds + 1):
            logger.info("Session %s: Dispatch round %d/%d", session.session_id, round_num, max_rounds)

            # Select workers based on playbook
            workers = self._select_workers(session.playbook)

            # Build session context
            session_context = {
                "session_id": session.session_id,
                "user_request": session.user_request,
                "playbook": session.playbook.value,
                "zone": "ZONE_A",  # TODO: extract from router_result
                "findings": session.findings,
                "current_round": round_num,
            }

            # Parallel dispatch
            worker_results = self._dispatch_workers_parallel(workers, session_context)

            # Append findings
            for agent_name, result in worker_results:
                session.findings.append({
                    "agent_name": agent_name,
                    "recommendation": result.get("recommendation", ""),
                    "ready_for_next_stage": result.get("ready_for_next_stage", False),
                    "evidence_refs": self._extract_evidence_refs(result),
                    "findings": result.get("findings", []),
                })

                # Emit event
                event = AgentEvent(
                    session_id=session.session_id,
                    agent_name=agent_name,
                    phase="DISPATCHING",
                    sequence=len(session.events),
                    timestamp_iso=to_iso(time.time()),
                    status="COMPLETED",
                    result_summary=result.get("recommendation", ""),
                    llm_call=result.get("llm_call_metadata"),
                    duration_ms=result.get("duration_ms", 0),
                )
                session.events.append(event)
                self._emit_event(session, agent_name, result)

            # Check ready_to_act with Coordinator
            coordinator_context = {**session_context, "current_round": round_num}
            coordinator_result = self.coordinator.execute(coordinator_context)

            # Emit coordinator event
            event = AgentEvent(
                session_id=session.session_id,
                agent_name="Coordinator",
                phase="DISPATCHING",
                sequence=len(session.events),
                timestamp_iso=to_iso(time.time()),
                status="COMPLETED",
                result_summary=coordinator_result["reasoning"],
                llm_call=coordinator_result["llm_call_metadata"],
                duration_ms=coordinator_result["duration_ms"],
            )
            session.events.append(event)
            self._emit_event(session, "Coordinator", coordinator_result)

            if coordinator_result["ready_to_act"]:
                logger.info("Session %s: ready_to_act=True after round %d", session.session_id, round_num)
                break

        return session

    def _act(self, session: AgentSession) -> AgentSession:
        """Phase 3: ACTING — create action plan, validate with Policy Gate."""
        session.state = SessionState.ACTING
        logger.info("Session %s: ACTING", session.session_id)

        # Build context for Action Agent
        action_context = {
            "session_id": session.session_id,
            "user_request": session.user_request,
            "findings": session.findings,
        }

        action_result = self.action.execute(action_context)

        if not action_result.get("action_plan"):
            session.state = SessionState.FAILED
            logger.error("Session %s: Action Agent failed to create plan", session.session_id)
            return session

        session.action_plan = action_result["action_plan"]

        # Emit event
        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Action",
            phase="ACTING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=f"Created {session.action_plan.schedule_id}",
            llm_call=action_result.get("llm_call_metadata"),
            duration_ms=action_result.get("duration_ms", 0),
        )
        session.events.append(event)
        self._emit_event(session, "Action", action_result)

        # Policy Gate validation (deterministic code)
        policy_result = self.policy_gate.validate(session.action_plan, action_context)

        if not policy_result.passed:
            session.state = SessionState.FAILED
            logger.warning("Session %s: Policy Gate failed: %s", session.session_id, policy_result.violations)
            self._emit_event(session, "PolicyGate", {"passed": False, "violations": policy_result.violations})
            return session

        if policy_result.approval_required:
            session.state = SessionState.AWAITING_APPROVAL
            logger.info("Session %s: Requires human approval", session.session_id)
            # Emit plan to Kafka
            self.kafka_producer.send_plan(self._serialize_plan(session.action_plan))
            return session

        # Emit plan to Kafka
        self.kafka_producer.send_plan(self._serialize_plan(session.action_plan))

        return session

    def _verify(self, session: AgentSession) -> AgentSession:
        """Phase 4: VERIFYING — independent verification."""
        session.state = SessionState.VERIFYING
        logger.info("Session %s: VERIFYING", session.session_id)

        verification_context = {
            "session_id": session.session_id,
            "findings": session.findings,
        }

        verification_result = self.verifier.verify(session.action_plan, verification_context)

        session.verification_result = verification_result

        # Emit event
        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Verifier",
            phase="VERIFYING",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary=f"Verdict: {verification_result.verdict.value}",
            llm_call=None,  # Verifier is deterministic code
            duration_ms=0,
        )
        session.events.append(event)

        # Emit verification to Kafka
        self.kafka_producer.send_verification(self._serialize_verification(verification_result))

        if verification_result.verdict.value != "VERIFIED":
            session.state = SessionState.FAILED
            logger.error("Session %s: Verification failed: %s", session.session_id, verification_result.verdict)
            return session

        return session

    def _narrate(self, session: AgentSession) -> AgentSession:
        """Phase 5: NARRATIVE — generate Vietnamese explanation."""
        logger.info("Session %s: NARRATIVE", session.session_id)

        narrative_context = {
            "user_request": session.user_request,
            "action_plan": session.action_plan,
            "findings": session.findings,
            "verification_result": session.verification_result,
        }

        narrative_result = self.narrative.execute(narrative_context)

        if narrative_result.get("narrative"):
            session.narrative = narrative_result["narrative"]

        # Emit event
        event = AgentEvent(
            session_id=session.session_id,
            agent_name="Narrative",
            phase="NARRATIVE",
            sequence=len(session.events),
            timestamp_iso=to_iso(time.time()),
            status="COMPLETED",
            result_summary="Narrative generated",
            llm_call=narrative_result.get("llm_call_metadata"),
            duration_ms=narrative_result.get("duration_ms", 0),
        )
        session.events.append(event)
        self._emit_event(session, "Narrative", narrative_result)

        return session

    def _select_workers(self, playbook) -> list[tuple[str, any]]:
        """Select workers based on playbook.

        For PLAN_IRRIGATION: [FieldIoT, Agronomy, Resource]
        """
        if playbook.value == "PLAN_IRRIGATION":
            return [
                ("FieldIoT", self.field_iot),
                ("Agronomy", self.agronomy),
                ("Resource", self.resource),
            ]
        # Add other playbooks as needed
        return []

    def _dispatch_workers_parallel(self, workers: list[tuple[str, any]], context: dict) -> list[tuple[str, dict]]:
        """Dispatch workers in parallel using ThreadPoolExecutor."""
        results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(worker.execute, context): name for name, worker in workers}

            for future in as_completed(futures):
                worker_name = futures[future]
                try:
                    result = future.result(timeout=30)
                    results.append((worker_name, result))
                except Exception as exc:
                    logger.error("Worker %s failed: %s", worker_name, exc)
                    results.append((worker_name, {"error": str(exc), "ready_for_next_stage": False}))

        return results

    def _extract_evidence_refs(self, result: dict) -> list[str]:
        """Extract all evidence_refs from worker result."""
        evidence_refs = []

        # Direct evidence_refs field
        if "evidence_refs" in result:
            evidence_refs.extend(result["evidence_refs"])

        # Nested in findings
        for finding in result.get("findings", []):
            if "evidence_refs" in finding:
                evidence_refs.extend(finding["evidence_refs"])

        return evidence_refs

    def _emit_event(self, session: AgentSession, agent_name: str, result: dict) -> None:
        """Emit agent event to Kafka."""
        event_dict = {
            "session_id": session.session_id,
            "agent_name": agent_name,
            "sequence": len(session.events) - 1,
            "timestamp_iso": to_iso(time.time()),
            "result": result,
        }
        self.kafka_producer.send_agent_event(event_dict)

    def _serialize_plan(self, plan) -> dict:
        """Serialize IrrigationSchedule to dict for Kafka."""
        return {
            "schedule_id": plan.schedule_id,
            "session_id": plan.session_id,
            "zone": plan.zone,
            "start_time_iso": plan.start_time_iso,
            "duration_minutes": plan.duration_minutes,
            "target_volume_liters": plan.target_volume_liters,
            "priority": plan.priority.value,
            "status": plan.status.value,
            "reason_vi": plan.reason_vi,
            "confidence": plan.confidence.value,
            "evidence_refs": plan.evidence_refs,
        }

    def _serialize_verification(self, verification) -> dict:
        """Serialize VerificationResult to dict for Kafka."""
        return {
            "verification_id": verification.verification_id,
            "session_id": verification.session_id,
            "object_type": verification.object_type,
            "object_id": verification.object_id,
            "verdict": verification.verdict.value,
            "read_back_ok": verification.read_back_ok,
            "field_matches": verification.field_matches,
            "field_mismatches": verification.field_mismatches,
            "message_vi": verification.message_vi,
            "verified_at_iso": verification.verified_at_iso,
        }

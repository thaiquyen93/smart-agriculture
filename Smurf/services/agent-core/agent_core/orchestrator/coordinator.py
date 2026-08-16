"""Orchestrator — main run_session() state machine with parallel worker dispatch.

Follows Implementation Plan orchestration flow.
State transitions: CREATED → ROUTING → DISPATCHING → ACTING → VERIFYING → COMPLETED/FAILED
"""
from __future__ import annotations

import logging
import time
import uuid
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
from agent_core.llm.client import LLMClient
from agent_core.policy.gate import PolicyGate
from agent_core.schemas.session import (
    AgentEvent,
    AgentPhase,
    AgentSession,
    AgentStatus,
    DataMode,
    LLMCallMetadata,
    SessionState,
    event_to_dict,
)
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
        llm_client: LLMClient,
    ):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.kafka_producer = kafka_producer
        self.llm_client = llm_client

        # Initialize agents
        self.router = RouterAgent(store, ledger, settings, llm_client)
        self.coordinator = CoordinatorAgent(store, ledger, settings, llm_client)
        self.field_iot = FieldIoTAgent(store, ledger, settings, llm_client)
        self.agronomy = AgronomyAgent(store, ledger, settings, llm_client)
        self.resource = ResourceAgent(store, ledger, settings, llm_client)
        self.action = ActionAgent(store, ledger, settings, llm_client)
        self.narrative = NarrativeAgent(store, ledger, settings, llm_client)
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

            # 2. DISPATCHING (max N rounds per LLM_PROFILE)
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
            self._add_event(
                session,
                agent="Orchestrator",
                phase=AgentPhase.DONE,
                status=AgentStatus.FAILED,
                title_vi="Phiên thất bại",
                detail_vi=f"Lỗi không xử lý được: {exc}",
            )
            return session

    def _route(self, session: AgentSession) -> AgentSession:
        """Phase 1: ROUTING — classify user request into playbook."""
        session.state = SessionState.ROUTING
        logger.info("Session %s: ROUTING", session.session_id)

        router_result = self.router.execute(session.user_request)

        session.playbook = router_result["playbook"]

        self._add_event(
            session,
            agent="Router",
            phase=AgentPhase.ROUTER,
            status=AgentStatus.SUCCEEDED,
            title_vi="Router: đã phân loại yêu cầu",
            detail_vi=f"Playbook: {router_result['playbook'].value}, Zone: {router_result['zone']}",
            llm_call=router_result["llm_call_metadata"],
            duration_ms=router_result["duration_ms"],
        )

        return session

    def _dispatch(self, session: AgentSession) -> AgentSession:
        """Phase 2: DISPATCHING — parallel worker dispatch (bounded rounds)."""
        session.state = SessionState.DISPATCHING
        logger.info("Session %s: DISPATCHING", session.session_id)

        max_rounds = self.settings.llm_profile_config().max_dispatch_rounds

        for round_num in range(1, max_rounds + 1):
            logger.info("Session %s: Dispatch round %d/%d", session.session_id, round_num, max_rounds)

            # Select workers based on playbook
            workers = self._select_workers(session.playbook)

            # Build session context
            session_context = {
                "session_id": session.session_id,
                "user_request": session.user_request,
                "playbook": session.playbook.value,
                "zone": "ZONE_A",  # the only zone Track B's 6 devices belong to (agent_core.devices.ZONE)
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

                self._add_event(
                    session,
                    agent=agent_name,
                    phase=AgentPhase.WORKER,
                    status=AgentStatus.SUCCEEDED if result.get("ready_for_next_stage") else AgentStatus.STARTED,
                    title_vi=f"{agent_name}: hoàn tất round {round_num}",
                    detail_vi=result.get("recommendation", ""),
                    evidence_refs=self._extract_evidence_refs(result),
                    llm_call=result.get("llm_call_metadata"),
                    duration_ms=result.get("duration_ms", 0),
                )

            # Check ready_to_act with Coordinator
            coordinator_context = {**session_context, "current_round": round_num}
            coordinator_result = self.coordinator.execute(coordinator_context)

            self._add_event(
                session,
                agent="Coordinator",
                phase=AgentPhase.COORDINATOR,
                status=AgentStatus.SUCCEEDED,
                title_vi=f"Coordinator: round {round_num}",
                detail_vi=coordinator_result["reasoning"],
                llm_call=coordinator_result["llm_call_metadata"],
                duration_ms=coordinator_result["duration_ms"],
            )

            if coordinator_result["ready_to_act"]:
                logger.info("Session %s: ready_to_act=True after round %d", session.session_id, round_num)
                break

        # Best-effort data_completeness/mode for this session, derived from
        # how many workers ended the dispatch loop ready_for_next_stage=True
        # (M2 approximation — refine once workers surface a real ratio).
        ready_count = sum(1 for f in session.findings if f.get("ready_for_next_stage"))
        session.data_completeness = f"{ready_count}/{len(session.findings)}" if session.findings else "0/0"
        session.mode = DataMode.FULL if session.findings and ready_count == len(session.findings) else DataMode.PARTIAL

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
            "zone": "ZONE_A",
            "data_completeness": session.data_completeness,
        }

        action_result = self.action.execute(action_context)

        if not action_result.get("action_plan"):
            session.state = SessionState.FAILED
            logger.error("Session %s: Action Agent failed to create plan", session.session_id)
            self._add_event(
                session,
                agent="Action",
                phase=AgentPhase.ACTION,
                status=AgentStatus.FAILED,
                title_vi="Action Agent thất bại",
                detail_vi=action_result.get("error", "Không tạo được action plan"),
                llm_call=action_result.get("llm_call_metadata"),
                duration_ms=action_result.get("duration_ms", 0),
            )
            return session

        session.action_plan = action_result["action_plan"]

        self._add_event(
            session,
            agent="Action",
            phase=AgentPhase.ACTION,
            status=AgentStatus.SUCCEEDED,
            title_vi="Action: đã tạo kế hoạch",
            detail_vi=f"Created {session.action_plan.schedule_id}",
            evidence_refs=list(getattr(session.action_plan, "evidence_refs", [])),
            llm_call=action_result.get("llm_call_metadata"),
            duration_ms=action_result.get("duration_ms", 0),
        )

        # Policy Gate validation (deterministic code)
        policy_result = self.policy_gate.validate(session.action_plan, action_context)

        if not policy_result.passed:
            session.state = SessionState.FAILED
            logger.warning("Session %s: Policy Gate failed: %s", session.session_id, policy_result.violations)
            self._add_event(
                session,
                agent="PolicyGate",
                phase=AgentPhase.POLICY_GATE,
                status=AgentStatus.BLOCKED,
                title_vi="Policy Gate: chặn kế hoạch",
                detail_vi="; ".join(v.message_vi for v in policy_result.violations),
            )
            return session

        if policy_result.approval_required:
            session.state = SessionState.AWAITING_APPROVAL
            logger.info("Session %s: Requires human approval", session.session_id)
            self._add_event(
                session,
                agent="PolicyGate",
                phase=AgentPhase.POLICY_GATE,
                status=AgentStatus.AWAITING_APPROVAL,
                title_vi="Policy Gate: chờ duyệt",
                detail_vi=policy_result.approval_reason_vi,
            )
            self.kafka_producer.send_plan(self._serialize_plan(session.action_plan))
            return session

        self._add_event(
            session,
            agent="PolicyGate",
            phase=AgentPhase.POLICY_GATE,
            status=AgentStatus.SUCCEEDED,
            title_vi="Policy Gate: đạt",
            detail_vi="Kế hoạch qua mọi ràng buộc, không cần duyệt.",
        )

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

        self._add_event(
            session,
            agent="Verifier",
            phase=AgentPhase.VERIFY,
            status=AgentStatus.SUCCEEDED if verification_result.verdict.value == "VERIFIED" else AgentStatus.FAILED,
            title_vi="Verifier: kết quả",
            detail_vi=f"Verdict: {verification_result.verdict.value}",
            llm_call=LLMCallMetadata(used=False),  # Verifier is deterministic code
        )

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

        self._add_event(
            session,
            agent="Narrative",
            phase=AgentPhase.NARRATIVE,
            status=AgentStatus.SUCCEEDED if narrative_result.get("narrative") else AgentStatus.FAILED,
            title_vi="Narrative: đã sinh bản tin",
            detail_vi=narrative_result.get("error", "Narrative generated"),
            evidence_refs=list(session.narrative.evidence_refs) if session.narrative else [],
            llm_call=narrative_result.get("llm_call_metadata"),
            duration_ms=narrative_result.get("duration_ms", 0),
        )

        return session

    def _select_workers(self, playbook) -> list[tuple[str, any]]:
        """Select workers based on playbook.

        For PLAN_IRRIGATION: [FieldIoT, Agronomy, Resource]. The other 4
        playbooks are Router-only for M2 (roadmap only requires Scenario 1 =
        PLAN_IRRIGATION for this gate — see M2_BUGS_FOUND.md #14).
        """
        if playbook.value == "PLAN_IRRIGATION":
            return [
                ("FieldIoT", self.field_iot),
                ("Agronomy", self.agronomy),
                ("Resource", self.resource),
            ]
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

    def _add_event(
        self,
        session: AgentSession,
        *,
        agent: str,
        phase: AgentPhase,
        status: AgentStatus,
        title_vi: str,
        detail_vi: str,
        evidence_refs: list[str] | None = None,
        llm_call: LLMCallMetadata | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Build a real AgentEvent, append it (session.add_event assigns
        `seq`), and mirror it to Kafka — single source of truth for what an
        agent step looked like, instead of two divergent dict shapes."""
        event = AgentEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            session_id=session.session_id,
            seq=0,  # overwritten by session.add_event()
            emitted_at_iso=to_iso(time.time()),
            phase=phase,
            agent=agent,
            status=status,
            title_vi=title_vi,
            detail_vi=detail_vi or "",
            evidence_refs=evidence_refs or [],
            llm_call=llm_call if llm_call is not None else LLMCallMetadata(used=False),
        )
        session.add_event(event)
        self.kafka_producer.send_agent_event(event_to_dict(event))
        if duration_ms:
            logger.debug("Session %s: %s/%s took %dms", session.session_id, phase.value, agent, duration_ms)

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

"""Policy Gate — deterministic validation before action execution.

Rule 1 (CLAUDE.md): "LLM đề xuất, code định đoạt."
Policy Gate is pure code, never LLM. Enforces hard constraints.

Checks (docs/agent-core/02-agents-and-tools.md §B.7):
1. Tank level >= 20% (POLICY_MIN_TANK_LEVEL_PCT)
2. Volume > 500L → PENDING_APPROVAL
3. Pump status OK
4. Evidence freshness FRESH
5. Upper bounds: volume <= 2000L, duration <= 120min
"""
from __future__ import annotations

from agent_core.config import Settings
from agent_core.devices import DeviceId, Freshness, Metric
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.schemas.action import IrrigationSchedule
from agent_core.schemas.policy import PolicyResult, PolicyRuleCode, PolicyViolation
from agent_core.state.store import FarmStateStore


class PolicyGate:
    """Deterministic policy enforcement (no LLM)."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings):
        self.store = store
        self.ledger = ledger
        self.settings = settings

    def validate(self, plan: IrrigationSchedule, session_context: dict) -> PolicyResult:
        """Validate irrigation plan against policy constraints.

        Returns PolicyResult(passed, violations, approval_required).
        passed=False → session FAILS immediately.
        approval_required=True → status becomes PENDING_APPROVAL.
        """
        violations: list[PolicyViolation] = []
        approval_required = False
        approval_reason = ""

        # Rule 1: Tank level >= 20%
        tank_reading = self.store.latest(DeviceId.TANK_01, Metric.TANK_LEVEL)
        if not tank_reading:
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.MIN_TANK_LEVEL,
                    message_vi="Không có dữ liệu mực bồn — không thể xác minh đủ nước.",
                    current_value="UNKNOWN",
                    threshold=f"{self.settings.policy_min_tank_level_pct}%",
                )
            )
        elif tank_reading.value < self.settings.policy_min_tank_level_pct:
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.MIN_TANK_LEVEL,
                    message_vi=f"Mực bồn {tank_reading.value:.1f}% < ngưỡng tối thiểu {self.settings.policy_min_tank_level_pct}%.",
                    current_value=f"{tank_reading.value:.1f}%",
                    threshold=f"{self.settings.policy_min_tank_level_pct}%",
                )
            )

        # Rule 2: Volume > 500L → requires approval
        if plan.target_volume_liters > self.settings.policy_approval_threshold_liters:
            approval_required = True
            approval_reason = (
                f"Lượng nước {plan.target_volume_liters:.0f} L vượt ngưỡng tự động "
                f"{self.settings.policy_approval_threshold_liters:.0f} L."
            )

        # Rule 3: Upper bounds
        if plan.target_volume_liters > self.settings.policy_max_volume_liters:
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.MAX_VOLUME_LITERS,
                    message_vi=f"Lượng nước {plan.target_volume_liters:.0f} L vượt giới hạn {self.settings.policy_max_volume_liters:.0f} L.",
                    current_value=f"{plan.target_volume_liters:.0f} L",
                    threshold=f"{self.settings.policy_max_volume_liters:.0f} L",
                )
            )

        if plan.duration_minutes > self.settings.policy_max_duration_minutes:
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.MAX_DURATION_MINUTES,
                    message_vi=f"Thời gian {plan.duration_minutes} phút vượt giới hạn {self.settings.policy_max_duration_minutes} phút.",
                    current_value=f"{plan.duration_minutes} min",
                    threshold=f"{self.settings.policy_max_duration_minutes} min",
                )
            )

        # Rule 4: Pump status OK (use VALVE_ZONE_A as proxy in M2)
        valve_reading = self.store.latest(DeviceId.VALVE_ZONE_A, Metric.VALVE_STATUS)
        if valve_reading and valve_reading.value < 0:  # FAULT condition
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.PUMP_STATUS_OK,
                    message_vi="Bơm/van khu A đang lỗi — không thể tưới.",
                    current_value="FAULT",
                    threshold="OK",
                )
            )

        # Rule 5: Evidence freshness
        stale_evidence = []
        for ev_id in plan.evidence_refs:
            ev = self.ledger.resolve(ev_id)
            if ev and ev.freshness != Freshness.FRESH:
                stale_evidence.append(ev_id)

        if stale_evidence:
            violations.append(
                PolicyViolation(
                    rule_code=PolicyRuleCode.EVIDENCE_FRESHNESS,
                    message_vi=f"Evidence không FRESH: {', '.join(stale_evidence)}.",
                    current_value=f"{len(stale_evidence)} stale",
                    threshold="ALL FRESH",
                )
            )

        passed = len(violations) == 0

        return PolicyResult(
            passed=passed,
            violations=violations,
            approval_required=approval_required,
            approval_reason_vi=approval_reason,
            modified_plan=None,
        )

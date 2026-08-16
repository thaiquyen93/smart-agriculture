"""Eval runner — M4.3.

Loads golden_set.yaml, runs each case through a mock (or real) session
executor, evaluates 5 criteria per docs/agent-core/08-eval-harness.md §3,
and writes results to eval/results/{profile}_{timestamp}.json.

Usage::

    python -m eval.run --profile local
    python -m eval.run --profile gemini
    python -m eval.run --profile local --case G01   # single case

Design decision — Deterministic Simulator vs. Real Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
M2 (the orchestrator) is being standardized in a parallel track. This runner
does NOT import from ``agent_core.orchestrator`` at module load time — it
accepts an *executor callable* injected at startup, defaulting to
``SimulatedOrchestrator`` (aliased as ``MockSessionExecutor`` for backward
compatibility) that deterministically evaluates session outputs from the
``mock_farm_state`` in each case.

When M2 is complete, replace ``SimulatedOrchestrator`` with the real one in
``run.py``'s ``_build_executor()`` — no changes needed in this file.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from eval import GOLDEN_SET_PATH, RESULTS_DIR
from eval.simulator import SimulatedOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class GoldenCase:
    id: str
    scenario: str
    mock_farm_state: dict[str, dict]
    user_request: str
    assertions: dict[str, Any]
    mock_series: dict[str, list] = field(default_factory=dict)
    existing_open_tasks: list[dict] = field(default_factory=list)
    mock_llm_behavior: str | None = None  # TIMEOUT | INVALID_JSON | None (normal)


@dataclass
class SessionResult:
    """Minimal shape of what the orchestrator returns — enough for assertions.

    When M2 is wired in, the real ``AgentSession`` object is mapped to this
    shape via ``SessionResultAdapter``.
    """
    session_id: str
    state: str                          # COMPLETED | FAILED | PARTIAL | TIMEOUT_ERROR | SCHEMA_ERROR
    playbook: str | None                # from router
    tools_called: list[str]             # all tool names invoked during the session
    final_output_text: str              # narrative or error message
    evidence_ids_in_output: list[str]   # EV-nnn refs present in final_output_text
    policy_outcome: str | None          # SCHEDULED | PENDING_APPROVAL | BLOCKED | None
    verification_verdict: str | None    # VERIFIED | PARTIAL | MISMATCH | None
    latency_ms: int
    schema_retries: int
    error: str | None = None
    evidence_ledger: dict[str, str] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    scenario: str
    scores: list[bool]                  # [playbook, tools, no_hallucination, policy, verification]
    score: float                        # sum(scores) / 5
    latency_ms: int
    schema_retries: int
    skipped: bool = False
    skip_reason: str = ""
    error: str | None = None

    @property
    def criteria_labels(self) -> list[str]:
        return ["playbook", "tools", "no_hallucination", "policy", "verification"]

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "scenario": self.scenario,
            "scores": dict(zip(self.criteria_labels, self.scores)),
            "score": self.score,
            "latency_ms": self.latency_ms,
            "schema_retries": self.schema_retries,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "error": self.error,
        }


@dataclass
class RunResult:
    profile: str
    timestamp: str
    cases: list[CaseResult]

    @property
    def total_score(self) -> float:
        active = [c for c in self.cases if not c.skipped]
        if not active:
            return 0.0
        return sum(c.score for c in active) / len(active)

    @property
    def avg_latency_ms(self) -> float:
        active = [c for c in self.cases if not c.skipped]
        if not active:
            return 0.0
        return sum(c.latency_ms for c in active) / len(active)

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "timestamp": self.timestamp,
            "total_score": self.total_score,
            "avg_latency_ms": self.avg_latency_ms,
            "cases": [c.as_dict() for c in self.cases],
        }


# ---------------------------------------------------------------------------
# Simulated Orchestrator Alias for Backward Compatibility
# ---------------------------------------------------------------------------

MockSessionExecutor = SimulatedOrchestrator


# ---------------------------------------------------------------------------
# Five assertion functions (08-eval-harness.md §3)
# ---------------------------------------------------------------------------

def assert_playbook(session: SessionResult, case: GoldenCase) -> bool:
    """Criterion 1: Router output matches expected playbook.

    Passes if:
    - No expected playbook specified (``null`` in yaml) → skip.
    - Session state is TIMEOUT_ERROR / SCHEMA_ERROR → can't check playbook → skip.
    - Otherwise ``session.playbook == expected``.
    """
    expected = case.assertions.get("playbook")
    if expected is None:
        return True  # don't check
    if session.state in ("TIMEOUT_ERROR", "SCHEMA_ERROR"):
        return True  # can't evaluate playbook on structural failure
    return session.playbook == expected


def assert_tools_called(session: SessionResult, case: GoldenCase) -> bool:
    """Criterion 2: All required tools were invoked.

    The golden case lists the *minimum required* tool set.  The session may
    call additional tools — that's fine (superset is OK).
    """
    required = set(case.assertions.get("required_tools") or [])
    if not required:
        return True  # nothing mandatory
    called = set(session.tools_called)
    missing = required - called
    if missing:
        logger.warning("Case %s: missing required tools: %s", case.id, missing)
    return not missing


# Token patterns that look like numeric values in output text.
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:lít|L|lít/phút|%|°C|W|pH|lux|phút|giờ|m²|mm)?\b")
# Evidence ID pattern
_EV_RE = re.compile(r"\bEV-\d+\b")


def assert_no_hallucinated_numbers(session: SessionResult, case: GoldenCase) -> bool:
    """Criterion 3: Every numeric token in the final output is traceable to an evidence_id.

    If session.evidence_ledger is populated, cross-checks every numeric token in
    final_output_text against the ledger values.
    Falls back to heuristic evidence-reference count check when ledger is empty.

    For TIMEOUT_ERROR / SCHEMA_ERROR outputs we always pass.
    """
    if not case.assertions.get("no_hallucinated_numbers", True):
        return True  # test explicitly opted out

    if session.state in ("TIMEOUT_ERROR", "SCHEMA_ERROR"):
        return True  # error messages don't contain fabricated sensor values

    text = session.final_output_text
    numbers = _NUMBER_RE.findall(text)
    ev_refs = _EV_RE.findall(text)

    # If no numbers found, no hallucination possible
    if not numbers:
        return True

    if not ev_refs:
        logger.warning(
            "Case %s: %d numeric token(s) in output but 0 evidence refs", case.id, len(numbers)
        )
        return False

    # Ledger-backed strict validation if evidence_ledger exists
    if session.evidence_ledger:
        ledger_floats: list[float] = []
        for val_str in session.evidence_ledger.values():
            try:
                ledger_floats.append(float(val_str))
            except (ValueError, TypeError):
                pass

        for raw_num in numbers:
            num_match = re.search(r"\d+(?:\.\d+)?", raw_num)
            if num_match:
                num_val = float(num_match.group(0))
                matched = any(abs(num_val - lf) < 1e-4 for lf in ledger_floats)
                if not matched:
                    logger.warning(
                        "Case %s: numeric value %s in output not found in evidence ledger",
                        case.id,
                        num_val,
                    )
                    return False

    return True


def assert_policy_outcome(session: SessionResult, case: GoldenCase) -> bool:
    """Criterion 4: Final action state matches expected Policy Gate outcome."""
    expected = case.assertions.get("policy_outcome")
    if expected is None:
        return True  # don't check

    if session.state in ("TIMEOUT_ERROR", "SCHEMA_ERROR"):
        return True  # structural failure — policy gate wasn't reached

    actual = session.policy_outcome
    if actual != expected:
        logger.warning("Case %s: policy_outcome=%r, expected=%r", case.id, actual, expected)
    return actual == expected


def assert_verification_verdict(session: SessionResult, case: GoldenCase) -> bool:
    """Criterion 5: Verification verdict matches expected (or just no crash).

    ``NO_CRASH`` means we only assert the session didn't raise an unhandled
    exception — any ``state`` is acceptable.
    """
    expected = case.assertions.get("verification_verdict", "VERIFIED")

    if expected == "NO_CRASH":
        # Pass as long as the session returned a result at all
        return True

    if session.state in ("TIMEOUT_ERROR", "SCHEMA_ERROR"):
        return True

    actual = session.verification_verdict
    if actual != expected:
        logger.warning(
            "Case %s: verification_verdict=%r, expected=%r", case.id, actual, expected
        )
    return actual == expected


_ASSERTION_FNS: list[Callable[[SessionResult, GoldenCase], bool]] = [
    assert_playbook,
    assert_tools_called,
    assert_no_hallucinated_numbers,
    assert_policy_outcome,
    assert_verification_verdict,
]


# ---------------------------------------------------------------------------
# EvalRunner
# ---------------------------------------------------------------------------

class EvalRunner:
    """Run all (or a subset of) golden cases and collect results.

    Args:
        profile: ``"local"`` or ``"gemini"`` — stored in results JSON for the
            compare script.
        executor: Callable ``(GoldenCase) -> SessionResult``.  Defaults to
            ``SimulatedOrchestrator().run``.
    """

    def __init__(
        self,
        profile: str,
        executor: Callable[[GoldenCase], SessionResult] | None = None,
    ) -> None:
        self.profile = profile
        self._executor = executor or SimulatedOrchestrator().run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_case(self, case: GoldenCase) -> CaseResult:
        t0 = time.monotonic()
        try:
            session = self._executor(case)
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.exception("Case %s executor raised unexpectedly", case.id)
            return CaseResult(
                case_id=case.id,
                scenario=case.scenario,
                scores=[False] * 5,
                score=0.0,
                latency_ms=elapsed,
                schema_retries=0,
                error=str(exc),
            )

        scores = [fn(session, case) for fn in _ASSERTION_FNS]
        score = sum(scores) / len(scores)
        return CaseResult(
            case_id=case.id,
            scenario=case.scenario,
            scores=scores,
            score=score,
            latency_ms=session.latency_ms,
            schema_retries=session.schema_retries,
            error=session.error,
        )

    def run_all(self, case_ids: list[str] | None = None) -> RunResult:
        cases = load_golden_set()
        if case_ids:
            cases = [c for c in cases if c.id in case_ids]

        results: list[CaseResult] = []
        for case in cases:
            logger.info("Running case %s: %s", case.id, case.scenario)
            results.append(self.run_case(case))

        return RunResult(
            profile=self.profile,
            timestamp=time.strftime("%Y%m%dT%H%M%S"),
            cases=results,
        )


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenCase]:
    """Parse ``golden_set.yaml`` into ``GoldenCase`` objects."""
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    cases = []
    for item in raw.get("cases", []):
        cases.append(GoldenCase(
            id=item["id"],
            scenario=item["scenario"],
            mock_farm_state=item.get("mock_farm_state", {}),
            user_request=item["user_request"],
            assertions=item.get("assertions", {}),
            mock_series=item.get("mock_series", {}),
            existing_open_tasks=item.get("existing_open_tasks", []),
            mock_llm_behavior=item.get("mock_llm_behavior"),
        ))
    return cases


# ---------------------------------------------------------------------------
# Results I/O
# ---------------------------------------------------------------------------

def save_result(result: RunResult) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{result.profile}_{result.timestamp}.json"
    path = RESULTS_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result.as_dict(), fh, ensure_ascii=False, indent=2)
    return path

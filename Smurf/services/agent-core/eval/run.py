"""CLI entry point for the eval runner — M4.3.

Usage::

    cd services/agent-core
    python -m eval.run --profile local
    python -m eval.run --profile gemini
    python -m eval.run --profile local --case G01
    python -m eval.run --profile local --case G01 G06 G13

Output: eval/results/{profile}_{timestamp}.json + summary table on stdout.

Wiring real orchestrator (when M2 is complete)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Replace ``_build_executor(profile)`` with something like::

    from agent_core.orchestrator.coordinator import run_session
    from agent_core.state.store import FarmStateStore
    ...

    def real_executor(case: GoldenCase) -> SessionResult:
        store = FarmStateStore()
        _inject_mock_farm_state(store, case.mock_farm_state)
        session = run_session(case.user_request, store=store, settings=settings)
        return SessionResultAdapter.from_agent_session(session)

Until then ``SimulatedOrchestrator`` is used automatically.
"""
from __future__ import annotations

import argparse
import logging
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from eval.runner import EvalRunner, RunResult, load_golden_set, save_result

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


def _build_executor(profile: str):  # noqa: ANN201
    """Return the session executor for the given profile.

    Currently uses SimulatedOrchestrator — swap here when M2 is done.
    """
    # TODO(M2-complete): replace with real orchestrator executor
    # Example:
    #   from agent_core.orchestrator.coordinator import RealExecutor
    #   return RealExecutor(profile=profile).run
    from eval.simulator import SimulatedOrchestrator  # noqa: PLC0415
    return SimulatedOrchestrator().run


def _print_summary(result: RunResult) -> None:
    """Print a human-readable table to stdout."""
    print(f"\n{'=' * 70}")
    print(f"  Eval Results — profile={result.profile}  ts={result.timestamp}")
    print(f"{'=' * 70}")
    header = f"{'ID':<5} {'Score':>6}  {'Play':>5} {'Tool':>5} {'NoHal':>6} {'Policy':>7} {'Verif':>6}  {'ms':>7}  Scenario"
    print(header)
    print("-" * 70)
    for c in result.cases:
        if c.skipped:
            print(f"{c.case_id:<5}  SKIP — {c.skip_reason}")
            continue
        s = c.scores
        emoji = ["PASS" if v else "FAIL" for v in s]
        print(
            f"{c.case_id:<5} {c.score:>5.1%}  "
            f"{emoji[0]:>5} {emoji[1]:>5} {emoji[2]:>6} {emoji[3]:>7} {emoji[4]:>6}  "
            f"{c.latency_ms:>7}ms  {c.scenario[:40]}"
        )
    print("-" * 70)
    print(f"  Total: {result.total_score:.1%} over {len([c for c in result.cases if not c.skipped])} cases")
    print(f"  Avg latency: {result.avg_latency_ms:.0f}ms")
    print(f"{'=' * 70}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run agent-core eval harness (M4.3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        choices=["local", "gemini"],
        default="local",
        help="LLM profile to use (default: local)",
    )
    parser.add_argument(
        "--case",
        nargs="*",
        metavar="ID",
        help="Run only specific case IDs (e.g. G01 G06). Omit to run all 15.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to eval/results/",
    )
    args = parser.parse_args(argv)

    executor = _build_executor(args.profile)
    runner = EvalRunner(profile=args.profile, executor=executor)

    case_ids = args.case or None
    result = runner.run_all(case_ids=case_ids)

    _print_summary(result)

    if not args.no_save:
        path = save_result(result)
        print(f"Results saved to: {path}\n")

    # Exit code: 0 if total score >= 80%, 1 otherwise
    return 0 if result.total_score >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())

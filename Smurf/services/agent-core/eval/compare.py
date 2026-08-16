"""Compare eval results from two profiles — M4.4.

Reads the most recent result JSON for each profile from eval/results/ and
prints a side-by-side markdown table matching the format in
docs/agent-core/08-eval-harness.md §5.

Usage::

    cd services/agent-core
    python -m eval.compare
    python -m eval.compare --local eval/results/local_20260816T120000.json \\
                           --gemini eval/results/gemini_20260816T121500.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval import RESULTS_DIR


def _latest_result(profile: str) -> dict | None:
    """Return the parsed JSON of the most recently saved result for `profile`."""
    pattern = f"{profile}_*.json"
    files = sorted(RESULTS_DIR.glob(pattern), reverse=True)
    if not files:
        return None
    with open(files[0], encoding="utf-8") as fh:
        return json.load(fh)


def _score_str(scores: dict[str, bool]) -> str:
    """Format scores dict as '5/5' or '3/5 (tool, policy)'."""
    passed = sum(scores.values())
    total = len(scores)
    if passed == total:
        return f"{passed}/{total}"
    failed = [k for k, v in scores.items() if not v]
    labels = {"playbook": "play", "tools": "tool", "no_hallucination": "nohall",
               "policy": "policy", "verification": "verif"}
    failed_short = ", ".join(labels.get(f, f) for f in failed)
    return f"{passed}/{total} ({failed_short})"


def _print_comparison(local_data: dict | None, gemini_data: dict | None) -> None:
    """Print markdown table side-by-side."""
    if local_data is None and gemini_data is None:
        print("No results found. Run `python -m eval.run --profile local` first.")
        return

    # Build per-case lookup
    local_cases: dict[str, dict] = {}
    if local_data:
        for c in local_data.get("cases", []):
            local_cases[c["case_id"]] = c

    gemini_cases: dict[str, dict] = {}
    if gemini_data:
        for c in gemini_data.get("cases", []):
            gemini_cases[c["case_id"]] = c

    all_ids = sorted(set(local_cases) | set(gemini_cases))

    print("\n## Eval Comparison: local vs gemini\n")
    print(f"| Case | local: 5 criteria | gemini: 5 criteria | local latency | gemini latency |")
    print(f"|------|------------------|-------------------|---------------|----------------|")

    for cid in all_ids:
        lc = local_cases.get(cid)
        gc = gemini_cases.get(cid)

        l_score = _score_str(lc["scores"]) if lc and not lc.get("skipped") else "SKIP"
        g_score = _score_str(gc["scores"]) if gc and not gc.get("skipped") else "SKIP"
        l_lat = f"{lc['latency_ms']}ms" if lc and not lc.get("skipped") else "—"
        g_lat = f"{gc['latency_ms']}ms" if gc and not gc.get("skipped") else "—"

        print(f"| {cid} | {l_score} | {g_score} | {l_lat} | {g_lat} |")

    print("|------|------------------|-------------------|---------------|----------------|")

    def fmt_total(data: dict | None) -> str:
        if data is None:
            return "—"
        pct = data.get("total_score", 0)
        cases = data.get("cases", [])
        active = [c for c in cases if not c.get("skipped")]
        passing = sum(1 for c in active if c.get("score", 0) >= 1.0)
        total = len(active) * 5
        earned = sum(int(c.get("score", 0) * 5) for c in active)
        return f"**{earned}/{total}**"

    def fmt_avg_lat(data: dict | None) -> str:
        if data is None:
            return "—"
        return f"**avg {data.get('avg_latency_ms', 0):.0f}ms**"

    print(f"| **Tổng** | {fmt_total(local_data)} | {fmt_total(gemini_data)} | "
          f"{fmt_avg_lat(local_data)} | {fmt_avg_lat(gemini_data)} |")

    print()

    # Interpretation guide (08-eval-harness.md §6)
    print("### Đọc kết quả\n")
    if local_data:
        score = local_data.get("total_score", 0)
        if score >= 0.8:
            print("✅ **local** đạt ≥ 80% — giữ local, ưu thế offline là lợi thế pitching thật.")
        else:
            print("⚠️  **local** dưới 80% — xem chi tiết tiêu chí nào fail:")
            print("    - Tiêu chí 4/5 fail → lỗi code (Policy/Verify), sửa trước khi so provider.")
            print("    - Tiêu chí 1/2 fail → cân nhắc thu hẹp schema hoặc chuyển gemini.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare eval results from two profiles (M4.4)")
    parser.add_argument("--local",  type=Path, default=None, help="Path to local results JSON")
    parser.add_argument("--gemini", type=Path, default=None, help="Path to gemini results JSON")
    args = parser.parse_args(argv)

    if args.local:
        with open(args.local, encoding="utf-8") as fh:
            local_data = json.load(fh)
    else:
        local_data = _latest_result("local")

    if args.gemini:
        with open(args.gemini, encoding="utf-8") as fh:
            gemini_data = json.load(fh)
    else:
        gemini_data = _latest_result("gemini")

    _print_comparison(local_data, gemini_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())

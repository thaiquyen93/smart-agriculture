"""Compare eval results from two profiles — M4.4.

Reads the most recent result JSON for each profile from eval/results/ and
prints a side-by-side markdown table with delta columns matching the format in
docs/agent-core/08-eval-harness.md §4-5.

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

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    labels = {
        "playbook": "play",
        "tools": "tool",
        "no_hallucination": "nohall",
        "policy": "policy",
        "verification": "verif",
    }
    failed_short = ", ".join(labels.get(f, f) for f in failed)
    return f"{passed}/{total} ({failed_short})"


def _print_comparison(local_data: dict | None, gemini_data: dict | None) -> None:
    """Print markdown table side-by-side with Delta columns."""
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

    print("\n## Eval Comparison: local vs gemini (SIMULATED — không phải benchmark thật)\n")
    print(f"| Case | local: 5 criteria | gemini: 5 criteria | Δ Score | local latency | gemini latency | Δ Latency |")
    print(f"|------|------------------|-------------------|---------|---------------|----------------|-----------|")

    for cid in all_ids:
        lc = local_cases.get(cid)
        gc = gemini_cases.get(cid)

        l_valid = lc and not lc.get("skipped")
        g_valid = gc and not gc.get("skipped")

        l_score = _score_str(lc["scores"]) if l_valid else "SKIP"
        g_score = _score_str(gc["scores"]) if g_valid else "SKIP"
        l_lat = f"{lc['latency_ms']}ms" if l_valid else "—"
        g_lat = f"{gc['latency_ms']}ms" if g_valid else "—"

        if l_valid and g_valid:
            l_pass = sum(lc["scores"].values())
            g_pass = sum(gc["scores"].values())
            d_score = g_pass - l_pass
            d_score_str = f"+{d_score}" if d_score >= 0 else f"{d_score}"

            d_lat = gc["latency_ms"] - lc["latency_ms"]
            d_lat_str = f"+{d_lat}ms" if d_lat >= 0 else f"{d_lat}ms"
        else:
            d_score_str = "—"
            d_lat_str = "—"

        print(f"| {cid} | {l_score} | {g_score} | {d_score_str} | {l_lat} | {g_lat} | {d_lat_str} |")

    print("|------|------------------|-------------------|---------|---------------|----------------|-----------|")

    def fmt_total(data: dict | None) -> tuple[int, int, str]:
        if data is None:
            return 0, 0, "—"
        cases = data.get("cases", [])
        active = [c for c in cases if not c.get("skipped")]
        total = len(active) * 5
        earned = sum(sum(c.get("scores", {}).values()) for c in active)
        return earned, total, f"**{earned}/{total}**"

    def fmt_avg_lat(data: dict | None) -> tuple[float, str]:
        if data is None:
            return 0.0, "—"
        avg_lat = float(data.get("avg_latency_ms", 0.0))
        return avg_lat, f"**avg {avg_lat:.0f}ms**"

    l_earned, l_total, l_tot_str = fmt_total(local_data)
    g_earned, g_total, g_tot_str = fmt_total(gemini_data)

    if local_data and gemini_data:
        tot_diff = g_earned - l_earned
        tot_diff_str = f"**+{tot_diff}**" if tot_diff >= 0 else f"**{tot_diff}**"
        l_lat_val, l_lat_str = fmt_avg_lat(local_data)
        g_lat_val, g_lat_str = fmt_avg_lat(gemini_data)
        lat_diff = g_lat_val - l_lat_val
        lat_diff_str = f"**+{lat_diff:.0f}ms**" if lat_diff >= 0 else f"**{lat_diff:.0f}ms**"
    else:
        tot_diff_str = "—"
        lat_diff_str = "—"
        _, l_lat_str = fmt_avg_lat(local_data)
        _, g_lat_str = fmt_avg_lat(gemini_data)

    print(f"| **Tổng** | {l_tot_str} | {g_tot_str} | {tot_diff_str} | "
          f"{l_lat_str} | {g_lat_str} | {lat_diff_str} |")

    print()

    # Interpretation guide (08-eval-harness.md §6)
    print("### Đọc kết quả\n")
    if local_data:
        score = local_data.get("total_score", 0)
        if score >= 0.8:
            print("OK local đạt ≥ 80% — giữ local, ưu thế offline là lợi thế pitching thật.")
        else:
            print("Cảnh báo: local dưới 80% — xem chi tiết tiêu chí nào fail:")
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

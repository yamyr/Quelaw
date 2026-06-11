"""Smoke test for the curated demo scenarios.

    py -3.12 scripts/check_demo_scenarios.py

Runs every scenario in ``quelaw/demo.py`` through the offline heuristic pipeline
(the exact path demo mode uses) and asserts each citation lands on its expected
status and the overall risk matches. Prints a per-scenario table and exits
non-zero on any mismatch, so it doubles as a pre-demo confidence check.
"""
import pathlib
import sys

# Windows consoles default to cp1252 and choke on the emoji in scenario titles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw import demo  # noqa: E402
from quelaw.pipeline import check_draft  # noqa: E402
from quelaw.schema import STATUS_LABEL  # noqa: E402


def _find(results, needle):
    for r in results:
        if needle.lower() in r.citation.lower():
            return r
    return None


def run() -> int:
    failures = 0
    for sc in demo.SCENARIOS:
        # use_llm=False == exactly what demo mode runs.
        report, _ = check_draft(sc.draft, use_llm=False)
        print(f"\n=== {sc.title} ===")
        print(f"    risk: {report.risk_level} (expected {sc.expected_risk})")
        if report.risk_level != sc.expected_risk:
            failures += 1
            print(f"    ✗ RISK MISMATCH: got {report.risk_level}, want {sc.expected_risk}")

        for exp in sc.expected:
            r = _find(report.results, exp.match)
            if r is None:
                failures += 1
                print(f"    ✗ missing citation matching {exp.match!r}")
                continue
            ok = r.status == exp.status
            failures += 0 if ok else 1
            mark = "✓" if ok else "✗"
            got = STATUS_LABEL.get(r.status, r.status)
            want = STATUS_LABEL.get(exp.status, exp.status)
            detail = f"(want {want})" if not ok else ""
            print(f"    {mark} [{got:<22}] {r.citation}  {detail}")

    print("\n" + ("ALL SCENARIOS PASSED ✅" if failures == 0 else f"{failures} CHECK(S) FAILED ❌"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())

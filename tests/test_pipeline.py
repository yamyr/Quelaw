"""End-to-end pipeline tests over the bundled test memo.

Runs in the offline heuristic mode (no ChromaDB or API key needed), so it is
deterministic in CI. Verifies the verification statuses and summary match the
documented answer key in data/demo/test_memo_expected.md.

    py -3.12 -m pytest tests/test_pipeline.py
    py -3.12 tests/test_pipeline.py        # plain-assert fallback runner
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw.config import DEMO_DIR  # noqa: E402
from quelaw.pipeline import check_draft  # noqa: E402
from quelaw.schema import NOT_FOUND, UNCERTAIN, VERIFIED  # noqa: E402


def _report():
    text = (DEMO_DIR / "test_memo.txt").read_text(encoding="utf-8")
    report, _ = check_draft(text, use_llm=False)
    return report


def _find(report, needle):
    matches = [r for r in report.results if needle in r.citation]
    assert matches, f"no result containing {needle!r}"
    return matches[0]


def test_summary_counts_match_answer_key():
    s = _report().summary
    assert s["total"] == 10
    assert s["verified"] == 5
    assert s["not_found"] == 2
    assert s["uncertain"] == 1
    assert s["requires_review"] == 2


def test_overall_risk_is_high():
    assert _report().risk_level == "High"


def test_fabricated_case_is_not_found():
    assert _find(_report(), "Lim Wei Ming").status == NOT_FOUND


def test_wrong_year_citation_is_uncertain():
    assert _find(_report(), "[2016] SGCA 20").status == UNCERTAIN


def test_real_case_is_verified():
    assert _find(_report(), "[2007] SGCA 37").status == VERIFIED


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

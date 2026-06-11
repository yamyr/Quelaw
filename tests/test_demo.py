"""Tests for the curated demo scenarios.

Each scenario must produce its advertised report through the offline heuristic
pipeline (the path demo mode uses), so the live demo can't silently drift.

Runs under pytest, or standalone:  py -3.12 tests/test_demo.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw import demo  # noqa: E402
from quelaw.pipeline import check_draft  # noqa: E402


def _find(results, needle):
    for r in results:
        if needle.lower() in r.citation.lower():
            return r
    return None


def _check_scenario(sc) -> None:
    report, _ = check_draft(sc.draft, use_llm=False)
    assert report.risk_level == sc.expected_risk, (
        f"{sc.id}: risk {report.risk_level} != expected {sc.expected_risk}"
    )
    for exp in sc.expected:
        r = _find(report.results, exp.match)
        assert r is not None, f"{sc.id}: no citation matching {exp.match!r}"
        assert r.status == exp.status, (
            f"{sc.id}: {exp.match!r} -> {r.status}, expected {exp.status}"
        )


def test_hero_catches_fabricated_case():
    _check_scenario(demo.HERO)
    # The headline promise: the planted fake is flagged not-found.
    report, _ = check_draft(demo.HERO.draft, use_llm=False)
    fake = _find(report.results, "[2024] SGHC 412")
    assert fake is not None and fake.status == "not_found_in_dataset"
    assert report.risk_level == "High"


def test_clean_draft_stays_low_risk():
    _check_scenario(demo.CLEAN)
    report, _ = check_draft(demo.CLEAN.draft, use_llm=False)
    assert report.summary["not_found"] == 0
    assert report.summary["uncertain"] == 0
    assert report.risk_level == "Low"


def test_wrong_citation_is_uncertain_not_fake():
    _check_scenario(demo.WRONG_CITATION)
    report, _ = check_draft(demo.WRONG_CITATION.draft, use_llm=False)
    acb = _find(report.results, "[2016] SGCA 20")
    # Real case, wrong year: uncertain — never asserted as a fabrication.
    assert acb is not None and acb.status == "uncertain_match"


def test_mixed_memo_exercises_every_outcome():
    _check_scenario(demo.MIXED)
    report, _ = check_draft(demo.MIXED.draft, use_llm=False)
    s = report.summary
    assert s["verified"] >= 1
    assert s["uncertain"] >= 1
    assert s["requires_review"] >= 1
    assert s["not_found"] >= 1


def test_all_scenarios_have_unique_ids():
    ids = [sc.id for sc in demo.SCENARIOS]
    assert len(ids) == len(set(ids))


if __name__ == "__main__":
    for _sc in demo.SCENARIOS:
        _check_scenario(_sc)
        print(f"ok: {_sc.id}")
    print("All demo scenarios passed.")

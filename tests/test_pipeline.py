"""End-to-end pipeline tests over the bundled test memo.

Runs in the offline heuristic mode (no ChromaDB or API key needed), so it is
deterministic in CI. Verifies the verification statuses and summary match the
documented answer key in data/demo/test_memo_expected.md.

    py -3.14 -m pytest tests/test_pipeline.py
    py -3.14 tests/test_pipeline.py        # plain-assert fallback runner
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


def test_subsection_is_not_verified_from_parent_section():
    from quelaw.schema import REQUIRES_REVIEW

    report, citations = check_draft("See section 14(999) of the Civil Law Act.", use_llm=False)
    assert citations[0].section == "14(999)"
    assert report.results[0].status == REQUIRES_REVIEW


def test_adversarial_mismatched_case_name_is_uncertain():
    # Real neutral citation ([2007] SGCA 37 is Spandeck), but fabricated case name.
    draft = "Counsel relies on Fake Shipping Ltd v Bad Transport Pte Ltd [2007] SGCA 37."
    report, _ = check_draft(draft, use_llm=False)
    assert len(report.results) == 1
    assert report.results[0].status == UNCERTAIN


def test_suggested_fix_generated_for_uncertain_citation():
    draft = "On novel heads of loss, see ACB v Thomson Medical Pte Ltd [2016] SGCA 20."
    report, _ = check_draft(draft, use_llm=False)
    assert len(report.results) == 1
    r = report.results[0]
    assert r.status == UNCERTAIN
    assert r.suggested_fix is not None
    assert "[2017] SGCA 20" in r.suggested_fix


def test_paraphrased_quote_evidence_is_limited_for_present_and_absent_text():
    # Given a phrase present in the paraphrased Spandeck summary.
    draft_real_quote = (
        'In Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37, '
        'the court noted the "threshold requirement of factual foreseeability" applies.'
    )
    rep1, _ = check_draft(draft_real_quote, use_llm=False)
    assert len(rep1.results) == 1
    assert rep1.results[0].quote_evidence.status == "evidence_limited"

    # Given a phrase absent from the same incomplete summary.
    draft_fake_quote = (
        'In Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37, '
        'the court held that "strict liability applies automatically to maritime contracts".'
    )
    rep2, _ = check_draft(draft_fake_quote, use_llm=False)
    assert len(rep2.results) == 1
    assert rep2.results[0].quote_evidence.status == "evidence_limited"


def test_annotator_html_rendering_and_apply_fix():
    from quelaw.annotator import annotate_draft_html
    from quelaw.corrections import apply_corrections

    draft = "See ACB v Thomson Medical Pte Ltd [2016] SGCA 20."
    report, _ = check_draft(draft, use_llm=False)

    html_out = annotate_draft_html(draft, report.results)
    assert "<mark" in html_out
    assert "Uncertain match" in html_out

    fixed_draft = apply_corrections(draft, [result.correction for result in report.results if result.correction])
    assert "[2017] SGCA 20" in fixed_draft


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

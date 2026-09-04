import hashlib
import json

from quelaw.pipeline import check_draft
from quelaw.report import report_to_markdown
from quelaw.sandbox import dataset_cached


def test_repeated_findings_keep_identity_evidence_and_corrections_in_exports():
    draft = (
        'ACB v Thomson Medical Pte Ltd [2016] SGCA 20.\n\n'
        'ACB v Thomson Medical Pte Ltd [2016] SGCA 20.\n\n'
        '[2007] SGCA 37 states "threshold requirement of factual foreseeability".'
    )
    report, _ = check_draft(draft, use_llm=False)
    payload = report.to_dict()
    markdown = report_to_markdown(report)
    assert payload["schema_version"] == 2
    assert payload["draft_sha256"] == hashlib.sha256(draft.encode()).hexdigest()
    assert payload["dataset_fingerprint"] == dataset_cached().fingerprint
    assert payload["verifier"]["mode"] == "heuristic"
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["distinct_authorities"] == 2
    assert len({r["occurrence_id"] for r in payload["results"]}) == 3
    for result in payload["results"]:
        for key in ("occurrence_id", "status", "source_id"):
            assert result[key] in markdown
        for reason in result["review_reasons"]:
            assert reason in markdown
        if result["quote_evidence"]:
            assert result["quote_evidence"]["status"] in markdown
            assert result["quote_evidence"]["reason"] in markdown
        if result["correction"]:
            assert result["correction"]["replacement"] in markdown
            assert result["correction"]["expected_text"] in markdown
            assert result["correction"]["draft_sha256"] == payload["draft_sha256"]
    assert payload["draft_sha256"] in markdown
    assert payload["dataset_fingerprint"] in markdown
    assert json.loads(json.dumps(payload)) == payload


def test_quote_limit_raises_risk_for_a_matched_authority():
    report, _ = check_draft(
        '[2007] SGCA 37 states "threshold requirement of factual foreseeability".',
        use_llm=False,
    )
    assert report.results[0].status == "verified"
    assert report.results[0].quote_evidence.status == "evidence_limited"
    assert report.results[0].explanation not in report.results[0].review_reasons
    assert report.risk_level == "Medium"
    assert report.summary["reviewed_occurrences"] == 1


def test_report_uses_explicit_dataset_identity(tmp_path):
    from quelaw.provenance import load_dataset

    dataset = load_dataset(tmp_path)
    report, _ = check_draft("See [2007] SGCA 37.", use_llm=False, dataset=dataset)
    assert report.dataset_fingerprint == dataset.fingerprint
    assert report.results[0].status == "not_found_in_dataset"


def test_empty_report_has_unknown_risk_and_no_occurrences():
    report, _ = check_draft("Plain text only.", use_llm=False)
    assert report.risk_level == "Unknown"
    assert report.summary["total"] == report.summary["distinct_authorities"] == 0

import hashlib
import json
from html.parser import HTMLParser

import pytest
from markdown_it import MarkdownIt

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
    quote_evidence = report.results[0].quote_evidence
    assert quote_evidence is not None
    assert quote_evidence.status == "evidence_limited"
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


class _RenderedReport(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _render(markdown: str) -> _RenderedReport:
    rendered = _RenderedReport()
    rendered.feed(MarkdownIt("commonmark").render(markdown))
    return rendered


def _inline_values(markdown: str) -> list[str]:
    return [
        child.content for token in MarkdownIt("commonmark").parse(markdown)
        for child in token.children or [] if child.type == "code_inline"
    ]


def test_offline_draft_context_is_literal_in_commonmark_export() -> None:
    # Given an untrusted draft with active Markdown image/link syntax by an authority.
    draft = 'See [2007] SGCA 37 ![review image](https://tracker.invalid/pixel?memo=private-token) [open](https://tracker.invalid/redirect).'
    report, _ = check_draft(draft, use_llm=False)
    context = report.to_dict()["results"][0]["context_sentence"]
    # When an actual CommonMark renderer processes the downloadable report.
    markdown = report_to_markdown(report)
    rendered = _render(markdown)
    # Then the syntax remains visible without active network-facing elements.
    assert not {"img", "a", "script", "iframe"}.intersection(rendered.tags)
    assert json.dumps(context, ensure_ascii=False) in "".join(rendered.text)
    assert json.dumps(context, ensure_ascii=False) in _inline_values(markdown)


@pytest.mark.parametrize("payload", [
    '![model image](https://tracker.invalid/model) [follow](https://tracker.invalid/redirect)',
    '<img src="https://tracker.invalid/html"><script>alert("review")</script>',
    '` ![one](https://tracker.invalid/one) ` `` [two](https://tracker.invalid/two) ``',
    '``` </code><img src="https://tracker.invalid/fence"> ``` ````` [five](https://tracker.invalid/five) `````',
    'First line\n\n```\n![block](https://tracker.invalid/block)\n```\n\n<div>model HTML</div>',
])
def test_model_explanation_preserves_literal_content_in_commonmark(payload: str) -> None:
    # Given model-like explanation and review data containing hostile Markdown or HTML.
    report, _ = check_draft("See [2007] SGCA 37.", use_llm=False)
    result = report.results[0]
    result.explanation = payload
    result.review_reasons = (payload,)
    original = report.to_dict()
    # When the export is parsed by a real Markdown implementation.
    markdown = report_to_markdown(report)
    rendered = _render(markdown)
    # Then all model text survives literally and does not create active HTML elements.
    assert not {"img", "a", "script", "iframe", "div"}.intersection(rendered.tags)
    assert json.dumps(payload, ensure_ascii=False) in "".join(rendered.text)
    assert json.dumps(payload, ensure_ascii=False) in _inline_values(markdown)
    assert report.to_dict() == original

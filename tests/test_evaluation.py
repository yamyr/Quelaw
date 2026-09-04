import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/evaluation/v1/cases.jsonl"
BASELINE = ROOT / "data/evaluation/v1/baseline.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluate.py"), *args],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_cli_reports_independent_metrics_when_corpus_matches() -> None:
    # Given the checked-in engineering baseline.
    # When the public offline evaluation command runs.
    completed = _run("--baseline", str(BASELINE))
    # Then its machine-readable report separates extraction from verification.
    assert completed.returncode == 0, completed.stderr or completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["passed"] is True
    assert summary["cases_run"] >= 30
    assert summary["extraction"]["precision"] == 1.0
    assert summary["extraction"]["recall"] == 1.0
    assert summary["extraction"]["span_accuracy"] == 1.0
    assert summary["authority_confusion"]["verified"]["verified"] > 0
    assert summary["quote_outcomes"]
    assert summary["boundary_cases_run"] > 0


def test_cli_fails_when_one_expected_verified_authority_is_changed(tmp_path: Path) -> None:
    # Given a changed expected verdict; aggregate baseline scores cannot excuse it.
    cases = [json.loads(line) for line in CASES.read_text().splitlines()]
    case = next(item for item in cases if item["kind"] == "pipeline" and item["expected"]
                and item["expected"][0]["status"] == "verified")
    case["expected"][0]["status"] = "uncertain_match"
    changed = tmp_path / "changed.jsonl"
    changed.write_text("\n".join(json.dumps(item) for item in cases) + "\n")
    # When the public command evaluates the altered expectation.
    completed = _run("--cases", str(changed), "--baseline", str(BASELINE))
    # Then it rejects a material false-verification difference independently of hashes.
    assert completed.returncode == 1
    summary = json.loads(completed.stdout)
    assert any(item["field"].endswith("status") and item["actual"] == "verified"
               for item in summary["mismatches"])


def test_cli_uses_explicit_dataset_when_it_has_no_authorities(tmp_path: Path) -> None:
    # Given an empty valid dataset that differs from the bundled sandbox.
    empty = tmp_path / "empty"
    empty.mkdir()
    # When --dataset selects that directory.
    completed = _run("--dataset", str(empty))
    # Then matching corpus cases fail instead of silently using the sandbox.
    assert completed.returncode == 1
    summary = json.loads(completed.stdout)
    assert summary["authority_confusion"]["verified"]["not_found_in_dataset"] > 0


def test_evaluation_never_uses_network_when_credentials_are_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given credentials and network/retrieval/API tripwires.
    from quelaw import config, llm, vectorstore
    from quelaw.evaluation import evaluate

    def forbidden(*args: str, **kwargs: str) -> None:
        pytest.fail("offline evaluation attempted external access")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-offline-key")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-offline-key")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(vectorstore, "query", forbidden)
    monkeypatch.setattr(llm, "extract_citations", forbidden)
    monkeypatch.setattr(llm, "verify_citation", forbidden)
    # When the real evaluator runs all pipeline and boundary cases.
    summary = evaluate(ROOT / "data/sandbox", CASES, BASELINE)
    # Then the checked-in expectations still pass.
    assert summary.passed, summary.mismatches


def test_quote_status_counts_survive_a_matched_text_mismatch(tmp_path: Path) -> None:
    from quelaw.evaluation import evaluate

    # Given a correct quote state paired with an independently wrong text expectation.
    cases = [json.loads(line) for line in CASES.read_text().splitlines()]
    case = next(item for item in cases if item["id"] == "exact_original")
    case["expected"]["matched_text"] = "an incorrect expected excerpt"
    changed = tmp_path / "quote.jsonl"
    changed.write_text(json.dumps(case) + "\n")
    # When the boundary case is evaluated.
    summary = evaluate(ROOT / "data/sandbox", changed)
    # Then failure details and status counts remain separate.
    assert not summary.passed
    assert summary.quote_outcomes == {"match_in_available_text": {"match_in_available_text": 1}}


def test_extraction_span_error_cannot_pass_with_correct_result_offsets(monkeypatch: pytest.MonkeyPatch) -> None:
    from quelaw import evaluation
    from quelaw.provenance import Dataset
    from quelaw.schema import Citation, Report

    # Given a regressed extractor whose result retains a stale correct span.
    real_check = evaluation.check_draft

    def shifted_extraction(text: str, use_llm: bool = False, *, dataset: Dataset | None = None) -> tuple[Report, list[Citation]]:
        report, citations = real_check(text, use_llm=use_llm, dataset=dataset)
        if citations:
            citations[0].start_char += 1
        return report, citations

    monkeypatch.setattr(evaluation, "check_draft", shifted_extraction)
    # When the complete corpus is evaluated.
    summary = evaluation.evaluate(ROOT / "data/sandbox", CASES)
    # Then exact span errors fail despite otherwise matching verification results.
    assert not summary.passed
    assert summary.extraction.span_accuracy < 1.0


@pytest.mark.parametrize("field,value", [("source_excerpt", ""), ("source_excerpt", " "), ("source_title", "Invented title")])
def test_pipeline_source_invariants_reject_empty_or_unattached_evidence(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str,
) -> None:
    from quelaw import evaluation
    from quelaw.provenance import Dataset
    from quelaw.schema import Citation, Report

    # Given a regressed result with empty evidence or invented metadata without a source.
    real_check = evaluation.check_draft

    def bad_evidence(text: str, use_llm: bool = False, *, dataset: Dataset | None = None) -> tuple[Report, list[Citation]]:
        report, citations = real_check(text, use_llm=use_llm, dataset=dataset)
        for result in report.results:
            if (field == "source_excerpt" and result.source_id is not None) or (field == "source_title" and result.source_id is None):
                setattr(result, field, value)
        return report, citations

    monkeypatch.setattr(evaluation, "check_draft", bad_evidence)
    # When the corpus is evaluated against the original baseline.
    summary = evaluation.evaluate(ROOT / "data/sandbox", CASES, BASELINE)
    # Then metadata cannot imply unavailable evidence while the gate passes.
    assert not summary.passed


@pytest.mark.parametrize("field,value", [("status", "not_found_in_dataset"), ("manual_review_required", True), ("source_url", "https://example.com/wrong")])
def test_claude_boundary_rejects_material_adapter_regressions(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str | bool,
) -> None:
    from collections.abc import Sequence
    from quelaw import evaluation_boundaries
    from quelaw.evaluation import evaluate
    from quelaw.evidence import ClaudeVerdict
    from quelaw.provenance import SourceRecord
    from quelaw.schema import Citation, VerificationResult

    # Given a controlled adapter regression after a valid source-two payload.
    real_adapt = evaluation_boundaries.adapt_verdict

    def bad_adapter(citation: Citation, verdict: ClaudeVerdict, candidates: Sequence[SourceRecord]) -> VerificationResult:
        result = real_adapt(citation, verdict, candidates)
        setattr(result, field, value)
        return result

    monkeypatch.setattr(evaluation_boundaries, "adapt_verdict", bad_adapter)
    # When real parsing and adaptation run through the corpus.
    summary = evaluate(ROOT / "data/sandbox", CASES, BASELINE)
    # Then changing a material verdict or source link fails the gate.
    assert not summary.passed


def test_quote_boundary_rejects_a_missing_review_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from quelaw import evaluation_boundaries
    from quelaw.evaluation import evaluate
    from quelaw.evidence import QuoteEvidence
    from quelaw.provenance import SourceRecord

    # Given correct quote fields with their required explanation removed.
    real_assess = evaluation_boundaries.assess_quote

    def no_reason(quote: str, source: SourceRecord) -> QuoteEvidence:
        return replace(real_assess(quote, source), reason="")

    monkeypatch.setattr(evaluation_boundaries, "assess_quote", no_reason)
    # When the corpus evaluates the real quote states.
    summary = evaluate(ROOT / "data/sandbox", CASES, BASELINE)
    # Then a missing review explanation is a material failure.
    assert not summary.passed

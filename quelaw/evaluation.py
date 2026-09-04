from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import assert_never

from pydantic import JsonValue

from .evaluation_boundaries import evaluate_claude, evaluate_correction, evaluate_quote
from .evaluation_types import (
    CASE_ADAPTER, Baseline, ClaudeCase, CorrectionCase, EvaluationCase,
    EvaluationSummary, ExpectedOccurrence, ExpectedQuote, ExtractionMetrics,
    Mismatch, PipelineCase, QuoteCase,
)
from .pipeline import check_draft
from .provenance import Dataset, load_dataset
from .schema import Citation, VerificationResult


class EvaluationInputError(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)


def load_cases(path: Path) -> tuple[EvaluationCase, ...]:
    cases = tuple(CASE_ADAPTER.validate_json(line) for line in path.read_bytes().splitlines() if line.strip())
    if not cases:
        raise EvaluationInputError("evaluation corpus is empty")
    if len({case.id for case in cases}) != len(cases):
        raise EvaluationInputError("evaluation case IDs must be unique")
    for case in cases:
        match case:
            case PipelineCase():
                previous_end = 0
                for expected in case.expected:
                    if expected.start_char < previous_end or case.draft[expected.start_char:expected.end_char] != expected.raw_text:
                        raise EvaluationInputError(f"{case.id}: expected occurrence span does not match the supplied draft")
                    previous_end = expected.end_char
            case QuoteCase() | CorrectionCase() | ClaudeCase():
                continue
            case unreachable:
                assert_never(unreachable)
    return cases


def _project(citation: Citation, result: VerificationResult) -> ExpectedOccurrence:
    evidence = result.quote_evidence
    return ExpectedOccurrence(
        raw_text=citation.raw_text, type=citation.type,
        case_name=citation.case_name, citation=citation.citation, act=citation.act,
        section=citation.section, order=citation.order, rule=citation.rule,
        start_char=result.start_char, end_char=result.end_char,
        authority_key=result.authority_key, status=result.status, source_id=result.source_id,
        quote_text=result.quote_text,
        quote_evidence=ExpectedQuote(status=evidence.status, source_id=evidence.source_id,
                                     matched_text=evidence.matched_text) if evidence else None,
        manual_review_required=result.manual_review_required,
        correction_replacement=result.correction.replacement if result.correction else None,
    )


def _different(case_id: str, field: str, expected: JsonValue, actual: JsonValue) -> tuple[Mismatch, ...]:
    if expected == actual:
        return ()
    return (Mismatch(case_id=case_id, field=field, expected=expected, actual=actual),)


def _identity(citation: Citation | ExpectedOccurrence) -> tuple[str | None, ...]:
    return (citation.type, citation.case_name, citation.citation,
            citation.act, citation.section, citation.order, citation.rule)


def _pipeline_mismatches(case: PipelineCase, dataset: Dataset) -> tuple[
    tuple[Mismatch, ...], tuple[int, int, int, int], tuple[tuple[str, str], ...], tuple[tuple[str, str], ...],
]:
    report, citations = check_draft(case.draft, use_llm=False, dataset=dataset)
    failures: list[Mismatch] = []
    material = report.to_dict()
    for field, expected in {"schema_version": 2, "draft_sha256": hashlib.sha256(case.draft.encode()).hexdigest(),
                            "dataset_fingerprint": dataset.fingerprint}.items():
        failures.extend(_different(case.id, field, expected, material.get(field)))
    failures.extend(_different(case.id, "verifier", {"mode": "heuristic", "model": None}, material.get("verifier")))
    failures.extend(_different(case.id, "occurrence_count", len(case.expected), len(citations)))
    failures.extend(_different(case.id, "result_count", len(case.expected), len(report.results)))
    expected_identities = Counter(_identity(item) for item in case.expected)
    observed_identities = Counter(_identity(item) for item in citations)
    correct = sum((expected_identities & observed_identities).values())
    expected_spans = Counter((_identity(item), item.start_char, item.end_char, item.raw_text) for item in case.expected)
    actual_spans = Counter((_identity(item), item.start_char, item.end_char, item.raw_text) for item in citations)
    exact = sum((expected_spans & actual_spans).values())
    authorities: list[tuple[str, str]] = []
    quotes: list[tuple[str, str]] = []
    sources = {source.document_id: source for source in dataset.records}
    for index, expected in enumerate(case.expected):
        if index >= len(citations) or index >= len(report.results):
            authorities.append((expected.status, "missing"))
            if expected.quote_evidence:
                quotes.append((expected.quote_evidence.status, "missing"))
            continue
        result = report.results[index]
        actual = _project(citations[index], result)
        actual_fields = actual.model_dump(mode="json")
        for field, value in expected.model_dump(mode="json").items():
            failures.extend(_different(case.id, f"occurrences[{index}].{field}", value, actual_fields[field]))
        for field, wanted, found in (
            ("extraction_start", expected.start_char, citations[index].start_char),
            ("extraction_end", expected.end_char, citations[index].end_char),
            ("result_citation", expected.raw_text, result.citation),
            ("result_type", expected.type, result.type),
        ):
            failures.extend(_different(case.id, f"occurrences[{index}].{field}", wanted, found))
        failures.extend(_different(case.id, f"occurrences[{index}].occurrence_id",
                                    f"{expected.start_char}:{expected.end_char}", result.occurrence_id))
        failures.extend(_different(case.id, f"occurrences[{index}].verifier", "heuristic", result.verifier))
        failures.extend(_different(case.id, f"occurrences[{index}].fallback_reason", None, result.fallback_reason))
        if result.quote_evidence is not None and not result.quote_evidence.reason.strip():
            failures.append(Mismatch(case_id=case.id, field=f"occurrences[{index}].quote_reason",
                                     expected="nonempty reason", actual=result.quote_evidence.reason))
        if expected.manual_review_required and not any(reason.strip() for reason in result.review_reasons):
            failures.append(Mismatch(case_id=case.id, field=f"occurrences[{index}].review_reasons",
                                     expected="nonempty review reasons", actual=list(result.review_reasons)))
        if result.correction is not None:
            proposal = result.correction
            for field, wanted, found in (
                ("draft_sha256", hashlib.sha256(case.draft.encode()).hexdigest(), proposal.draft_sha256),
                ("start_char", expected.start_char, proposal.start_char),
                ("end_char", expected.end_char, proposal.end_char),
                ("expected_text", expected.raw_text, proposal.expected_text),
            ):
                failures.extend(_different(case.id, f"occurrences[{index}].correction.{field}", wanted, found))
        if result.source_id in sources:
            source = sources[result.source_id]
            failures.extend(_different(case.id, f"occurrences[{index}].source_provenance",
                                        source.provenance.model_dump(mode="json"),
                                        result.source_provenance.model_dump(mode="json") if result.source_provenance else None))
            failures.extend(_different(case.id, f"occurrences[{index}].source_title", source.title, result.source_title))
            failures.extend(_different(case.id, f"occurrences[{index}].source_url",
                                        str(source.provenance.official_url) if source.provenance.official_url else None, result.source_url))
            if not result.source_excerpt or not result.source_excerpt.strip() or result.source_excerpt not in source.text:
                failures.append(Mismatch(case_id=case.id, field=f"occurrences[{index}].source_excerpt",
                                         expected="literal available source text", actual=result.source_excerpt))
        elif result.source_id is None:
            for field, found in (
                ("source_title", result.source_title), ("source_url", result.source_url),
                ("source_excerpt", result.source_excerpt),
                ("source_provenance", result.source_provenance.model_dump(mode="json") if result.source_provenance else None),
            ):
                failures.extend(_different(case.id, f"occurrences[{index}].{field}", None, found))
        authorities.append((expected.status, result.status))
        if expected.quote_evidence or actual.quote_evidence:
            quotes.append((expected.quote_evidence.status if expected.quote_evidence else "none",
                           actual.quote_evidence.status if actual.quote_evidence else "none"))
    return tuple(failures), (correct, len(citations), len(case.expected), exact), tuple(authorities), tuple(quotes)


def evaluate(dataset_path: Path, cases_path: Path, baseline_path: Path | None = None) -> EvaluationSummary:
    """Run local-only corpus cases; a baseline never excuses a material mismatch."""
    dataset = load_dataset(dataset_path)
    cases = load_cases(cases_path)
    corpus_hash = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    failures: list[Mismatch] = []
    tp = observed = expected_count = exact = pipelines = 0
    authority_pairs: list[tuple[str, str]] = []
    quote_pairs: list[tuple[str, str]] = []
    for case in cases:
        match case:
            case PipelineCase():
                differences, counts, authorities, quotes = _pipeline_mismatches(case, dataset)
                failures.extend(differences)
                correct, found, wanted, spans = counts
                tp, observed, expected_count, exact = tp + correct, observed + found, expected_count + wanted, exact + spans
                pipelines += 1
                authority_pairs.extend(authorities)
                quote_pairs.extend(quotes)
            case QuoteCase():
                differences, actual = evaluate_quote(case)
                failures.extend(differences)
                quote_pairs.append((case.expected.status, actual))
            case CorrectionCase():
                failures.extend(evaluate_correction(case))
            case ClaudeCase():
                failures.extend(evaluate_claude(case))
            case unreachable:
                assert_never(unreachable)
    if baseline_path is not None:
        baseline = Baseline.model_validate_json(baseline_path.read_bytes())
        failures.extend(_different("baseline", "dataset_fingerprint", baseline.dataset_fingerprint, dataset.fingerprint))
        failures.extend(_different("baseline", "corpus_sha256", baseline.corpus_sha256, corpus_hash))
        failures.extend(_different("baseline", "case_count", baseline.case_count, len(cases)))
    return EvaluationSummary(
        dataset_fingerprint=dataset.fingerprint, corpus_sha256=corpus_hash,
        cases_run=len(cases), pipeline_cases_run=pipelines, boundary_cases_run=len(cases)-pipelines,
        extraction=ExtractionMetrics(true_positive=tp, false_positive=observed-tp,
                                     false_negative=expected_count-tp, exact_spans=exact,
                                     precision=tp / observed if observed else float(expected_count == 0),
                                     recall=tp / expected_count if expected_count else 1.0,
                                     span_accuracy=exact / expected_count if expected_count else 1.0),
        authority_confusion={label: dict(Counter(actual for wanted, actual in authority_pairs if wanted == label))
                             for label in sorted({wanted for wanted, _ in authority_pairs})},
        quote_outcomes={label: dict(Counter(actual for wanted, actual in quote_pairs if wanted == label))
                        for label in sorted({wanted for wanted, _ in quote_pairs})},
        mismatches=tuple(failures), passed=not failures,
    )

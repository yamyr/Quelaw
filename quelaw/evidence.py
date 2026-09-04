"""Bind authority decisions and quotations to the selected available source."""
from __future__ import annotations

import re
import urllib.parse
from collections.abc import Sequence

from .evidence_types import ClaudeVerdict, EvidenceValidationError, QuoteEvidence
from .heuristic import grounded_replacement, verify_heuristic
from .provenance import Dataset, SourceRecord
from .schema import Citation, VerificationResult


def matching_span(quote: str, text: str) -> str | None:
    """Return actual source wording for a contiguous normalized token sequence."""
    query = re.findall(r"\w+", quote.casefold())
    tokens = list(re.finditer(r"\w+", text))
    if not query:
        return None
    words = [token.group().casefold() for token in tokens]
    for index in range(len(words) - len(query) + 1):
        if words[index:index + len(query)] == query:
            return text[tokens[index].start():tokens[index + len(query) - 1].end()]
    return None


def assess_quote(quote: str, source: SourceRecord) -> QuoteEvidence:
    """Assess available original wording without upgrading paraphrases or excerpts."""
    provenance = source.provenance
    if provenance.text_kind != "original" or provenance.coverage == "summary":
        return QuoteEvidence(
            "evidence_limited", source.document_id, None,
            f"Available text is {provenance.text_kind} with {provenance.coverage} coverage; original quotation wording cannot be established.",
        )
    if not re.search(r"\w", quote):
        return QuoteEvidence("evidence_limited", source.document_id, None, "No quotation words are available to compare.")
    matched = matching_span(quote, source.text)
    if matched is not None:
        return QuoteEvidence(
            "match_in_available_text", source.document_id, matched,
            "A contiguous sequence matches the available original text after case and punctuation normalization; context and attribution still require review.",
        )
    if provenance.coverage != "complete":
        return QuoteEvidence(
            "evidence_limited", source.document_id, None,
            "The quotation was not located in the available excerpt; absence from the full document cannot be established.",
        )
    return QuoteEvidence(
        "not_found_in_available_text", source.document_id, None,
        "The quotation's contiguous word sequence was not found in the available original text.",
    )


def quote_for_citation(citation: Citation, source: SourceRecord | None) -> QuoteEvidence | None:
    """Respect extraction's attribution uncertainty before comparing source text."""
    if not citation.quote_text:
        return None
    if citation.quote_ambiguous:
        return QuoteEvidence(
            "ambiguous_attribution", None, None,
            "The surrounding context contains multiple authorities or quotations; attribution needs manual review.",
        )
    if source is None:
        return QuoteEvidence("evidence_limited", None, None, "No matching source text is available for this quotation.")
    return assess_quote(citation.quote_text, source)


def search_url(citation: Citation) -> str | None:
    """Offer a separately labelled external lookup without claiming source identity."""
    if citation.type == "case":
        query = citation.citation or citation.case_name or citation.raw_text
        return f"https://www.elitigation.sg/gd/Home/Index?SearchQuery={urllib.parse.quote_plus(query)}"
    if citation.type == "statute":
        return f"https://sso.agc.gov.sg/Search?Keyword={urllib.parse.quote_plus(citation.act or citation.raw_text)}"
    if citation.type == "rule":
        return "https://sso.agc.gov.sg/Search?Keyword=Rules+of+Court"
    return None


def attach_evidence(result: VerificationResult, citation: Citation, source: SourceRecord | None) -> VerificationResult:
    """Add traceable identity and quote review reasons to one occurrence finding."""
    result.occurrence_id = f"{citation.start_char}:{citation.end_char}"
    result.authority_key = citation.key()
    result.context_sentence = citation.context_sentence
    result.quote_text = citation.quote_text
    result.quote_evidence = quote_for_citation(citation, source)
    result.external_search_url = search_url(citation)
    reasons = [] if result.status == "verified" else [result.explanation]
    if source is not None:
        result.source_id = source.document_id
        result.source_title = source.title
        result.source_provenance = source.provenance
        result.source_url = str(source.provenance.official_url) if source.provenance.official_url else None
        if result.source_excerpt is None:
            result.source_excerpt = source.text[:320]
    if result.quote_evidence and result.quote_evidence.status != "match_in_available_text":
        reasons.append(result.quote_evidence.reason)
    if result.fallback_reason:
        reasons.append(result.fallback_reason)
    result.review_reasons = tuple(reasons)
    result.manual_review_required = result.manual_review_required or bool(reasons)
    return result


def adapt_verdict(citation: Citation, verdict: ClaudeVerdict, candidates: Sequence[SourceRecord]) -> VerificationResult:
    """Reject unsupported model evidence and derive display metadata from its source."""
    source = next((record for record in candidates if record.document_id == verdict.source_id), None)
    if verdict.source_id is not None and source is None:
        raise EvidenceValidationError("Claude selected an unknown source_id.")
    if source is not None and verdict.status == "not_found_in_dataset":
        raise EvidenceValidationError("Claude's not-found decision cannot attach a selected authority.")
    if source is None and (verdict.status != "not_found_in_dataset" or verdict.source_excerpt or verdict.suggested_fix):
        raise EvidenceValidationError("Claude's decision requires a selected candidate source.")
    if source and verdict.source_excerpt and verdict.source_excerpt not in source.text:
        raise EvidenceValidationError("Claude supplied an excerpt absent from the selected source.")
    if source and verdict.status == "verified":
        candidate_check = verify_heuristic(citation, Dataset(records=(source,), fingerprint="candidate-check"))
        if candidate_check.status != "verified":
            raise EvidenceValidationError("Claude's verified decision contradicts the selected source authority metadata.")
    replacement = grounded_replacement(citation, source) if source else None
    if verdict.suggested_fix and verdict.suggested_fix != replacement:
        raise EvidenceValidationError("Claude supplied a replacement unsupported by the selected source metadata.")
    result = VerificationResult(
        citation=citation.raw_text, type=citation.type, status=verdict.status,
        confidence=verdict.confidence, explanation=verdict.explanation,
        source_excerpt=verdict.source_excerpt, manual_review_required=verdict.manual_review_required,
        suggested_fix=verdict.suggested_fix, verifier="claude",
        start_char=citation.start_char, end_char=citation.end_char,
    )
    return attach_evidence(result, citation, source)

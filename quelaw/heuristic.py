"""Deterministic authority comparison over the explicitly supplied dataset."""
from __future__ import annotations

import re
from collections.abc import Sequence

from .provenance import Dataset, SourceRecord
from .schema import Citation, VerificationResult


def _norm_cite(value: str | None) -> str:
    return " ".join((value or "").upper().split())


def _norm_section(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").lower())


def _name_tokens(value: str | None) -> set[str]:
    stop = {"v", "vs", "pte", "ltd", "the", "of", "and", "co", "sdn", "bhd"}
    tokens = [match.group() for match in re.finditer(r"[a-z0-9]+", (value or "").lower())]
    return {token for token in tokens if token not in stop and len(token) > 1}


def _name_overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def _act_match(query: str, title: str) -> bool:
    query_words = re.sub(r"\b(the|act|code|ordinance)\b", "", query.lower()).strip()
    title_words = re.sub(r"\b(the|act|code|ordinance)\b", "", title.lower()).strip()
    return bool(query_words and title_words and (query_words in title_words or title_words in query_words))


def grounded_replacement(citation: Citation, source: SourceRecord) -> str | None:
    """Build a replacement only from the selected source's authority metadata."""
    replacements = {
        "case": (
            f"{source.title} {source.citation}" if citation.case_name else source.citation
        ) if source.citation else None,
        "statute": f"section {source.section} of the {source.title}" if source.section else None,
        "rule": f"Order {source.order} Rule {source.rule}" if source.order and source.rule else None,
    }
    return replacements[source.source_type]


def _finding(citation: Citation, status: str, confidence: float, explanation: str,
             source: SourceRecord | None = None, *, suggest: bool = False) -> VerificationResult:
    result = VerificationResult(
        citation=citation.raw_text, type=citation.type, status=status, confidence=confidence,
        explanation=explanation, manual_review_required=status != "verified",
        suggested_fix=grounded_replacement(citation, source) if source and suggest else None,
        source_id=source.document_id if source else None,
        start_char=citation.start_char, end_char=citation.end_char,
    )
    return result


def _not_found(citation: Citation) -> VerificationResult:
    return _finding(
        citation, "not_found_in_dataset", 0.2,
        "This authority was not found in the available dataset. It may be outside the current sandbox; manual review is required.",
    )


def _verify_case(citation: Citation, records: Sequence[SourceRecord]) -> VerificationResult:
    cases = [record for record in records if record.source_type == "case"]
    target = _norm_cite(citation.citation)
    if target:
        for record in cases:
            if _norm_cite(record.citation) != target:
                continue
            if citation.case_name and _name_overlap(_name_tokens(citation.case_name), _name_tokens(record.title)) < 0.2:
                return _finding(
                    citation, "uncertain_match", 0.5,
                    f"Citation {citation.citation} exists in the dataset, but the cited case name differs from '{record.title}'. Possible citation mismatch; manual review required.",
                    record, suggest=True,
                )
            return _finding(citation, "verified", 0.95, "Exact citation match found in the available sandbox dataset.", record)
    if citation.case_name:
        ranked = sorted(
            ((_name_overlap(_name_tokens(citation.case_name), _name_tokens(record.title)), record) for record in cases),
            key=lambda item: item[0], reverse=True,
        )
        if ranked and ranked[0][0] >= 0.5:
            score, record = ranked[0]
            return _finding(
                citation, "uncertain_match", round(0.4 + 0.2 * score, 2),
                f"A case with a similar name exists in the dataset ({record.title}), but the citation is {record.citation}. Possible typo or mismatch; manual review required.",
                record, suggest=True,
            )
    return _not_found(citation)


def _verify_statute(citation: Citation, records: Sequence[SourceRecord]) -> VerificationResult:
    matches = [record for record in records if record.source_type == "statute" and _act_match(citation.act or "", record.title)]
    section = _norm_section(citation.section)
    for record in matches:
        if section and _norm_section(record.section) == section:
            return _finding(
                citation, "verified", 0.9,
                f"Section {citation.section} of the {record.title} was found in the available dataset.", record,
            )
    if matches:
        record = matches[0]
        return _finding(
            citation, "requires_manual_review", 0.5,
            f"The {record.title} exists in the dataset, but section {citation.section} could not be confirmed. Manual review of the specific provision required.", record,
        )
    return _not_found(citation)


def _verify_rule(citation: Citation, records: Sequence[SourceRecord]) -> VerificationResult:
    rules = [record for record in records if record.source_type == "rule"]
    for record in rules:
        provision = re.fullmatch(r"\s*Order\s+(\d+)\s+Rule\s+(\d+(?:\([\da-zA-Z]+\))*)\s*", record.provision or "", re.IGNORECASE)
        order = record.order or (provision.group(1) if provision else None)
        rule = record.rule or (provision.group(2) if provision else None)
        if citation.order and citation.rule and order == citation.order and rule == citation.rule:
            return _finding(
                citation, "verified", 0.9,
                f"{record.provision or f'Order {order} Rule {rule}'} was found in the available dataset ({record.title}).", record,
            )
    if rules:
        return _finding(
            citation, "requires_manual_review", 0.4,
            f"The {rules[0].title} is in the dataset, but Order {citation.order} Rule {citation.rule} could not be confirmed. Manual review required.", rules[0],
        )
    return _not_found(citation)


def verify_heuristic(citation: Citation, dataset: Dataset) -> VerificationResult:
    """Preserve existing authority statuses while binding evidence to typed records."""
    if citation.type == "case":
        return _verify_case(citation, dataset.records)
    if citation.type == "statute":
        return _verify_statute(citation, dataset.records)
    if citation.type == "rule":
        return _verify_rule(citation, dataset.records)
    return _not_found(citation)

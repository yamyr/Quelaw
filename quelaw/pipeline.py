"""End-to-end orchestration: draft text -> verification report.

    Paste draft -> extract citations -> retrieve from sandbox -> verify -> report
"""
from __future__ import annotations

import hashlib

from .extraction import extract_citations
from .report import build_report
from .provenance import Dataset
from .sandbox import load_current_dataset
from .schema import Citation, CorrectionProposal, Report
from .verification import verify_all


def check_draft(
    text: str, use_llm: bool | None = None, *, dataset: Dataset | None = None,
) -> tuple[Report, list[Citation]]:
    """Run the full pipeline on a draft. Returns ``(report, citations)``."""
    sources = dataset if dataset is not None else load_current_dataset()
    draft_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    citations = extract_citations(text, use_llm=use_llm)
    results = verify_all(citations, use_llm=use_llm, dataset=sources)
    for citation, result in zip(citations, results, strict=True):
        if result.suggested_fix and 0 <= citation.start_char < citation.end_char <= len(text):
            expected = text[citation.start_char:citation.end_char]
            if expected == citation.raw_text and result.suggested_fix != expected:
                result.correction = CorrectionProposal(
                    draft_sha256=draft_sha256,
                    start_char=citation.start_char, end_char=citation.end_char,
                    expected_text=expected, replacement=result.suggested_fix,
                )
    return build_report(
        results, draft_sha256=draft_sha256, dataset_fingerprint=sources.fingerprint,
    ), citations

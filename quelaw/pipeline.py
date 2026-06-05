"""End-to-end orchestration: draft text -> verification report.

    Paste draft -> extract citations -> retrieve from sandbox -> verify -> report
"""
from __future__ import annotations

from typing import List, Tuple

from .extraction import extract_citations
from .report import build_report
from .schema import Citation, Report
from .verification import verify_all


def check_draft(text: str, use_llm: bool | None = None) -> Tuple[Report, List[Citation]]:
    """Run the full pipeline on a draft. Returns ``(report, citations)``."""
    citations = extract_citations(text, use_llm=use_llm)
    results = verify_all(citations, use_llm=use_llm)
    return build_report(results), citations

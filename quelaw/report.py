"""Report assembly: summary statistics and an overall risk level."""
from __future__ import annotations

from typing import List

from .schema import (
    DISCLAIMER,
    NOT_FOUND,
    REQUIRES_REVIEW,
    UNCERTAIN,
    VERIFIED,
    Report,
    VerificationResult,
)


def build_report(results: List[VerificationResult]) -> Report:
    summary = {
        "total": len(results),
        "verified": sum(r.status == VERIFIED for r in results),
        "not_found": sum(r.status == NOT_FOUND for r in results),
        "uncertain": sum(r.status == UNCERTAIN for r in results),
        "requires_review": sum(r.status == REQUIRES_REVIEW for r in results),
    }

    if summary["total"] == 0:
        level, detail = "Unknown", "No legal authorities were detected in the draft."
    elif summary["not_found"] > 0:
        level, detail = (
            "High",
            "One or more cited authorities were not found in the trusted dataset. "
            "Possible hallucination — manual review strongly recommended.",
        )
    elif summary["uncertain"] or summary["requires_review"]:
        level, detail = (
            "Medium",
            "Some authorities need manual review (partial match, version, or "
            "provision could not be confirmed).",
        )
    else:
        level, detail = (
            "Low",
            "All detected authorities were matched in the trusted dataset. Manual "
            "review against official sources is still recommended before use.",
        )

    return Report(
        summary=summary,
        results=results,
        risk_level=level,
        risk_detail=detail,
        disclaimer=DISCLAIMER,
    )

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


def report_to_markdown(report: Report) -> str:
    """Format a verification report as a structured Markdown document."""
    from .schema import STATUS_ICON, STATUS_LABEL

    s = report.summary
    lines = [
        "# Quelaw Verification Report",
        "",
        f"**Overall Risk:** {report.risk_level} — {report.risk_detail}",
        "",
        "## Summary",
        f"- **Total Authorities:** {s.get('total', 0)}",
        f"- **Verified in Dataset:** {s.get('verified', 0)}",
        f"- **Not Found in Dataset:** {s.get('not_found', 0)}",
        f"- **Uncertain Match:** {s.get('uncertain', 0)}",
        f"- **Requires Manual Review:** {s.get('requires_review', 0)}",
        "",
        "## Citations",
        "",
    ]

    if not report.results:
        lines.append("No legal authorities were detected in the draft.")
    else:
        for i, r in enumerate(report.results, 1):
            icon = STATUS_ICON.get(r.status, "•")
            label = STATUS_LABEL.get(r.status, r.status)
            lines.append(f"### {i}. {r.citation}")
            lines.append(f"- **Type:** `{r.type}`")
            lines.append(f"- **Status:** {icon} **{label}** (confidence: {r.confidence:.0%})")
            lines.append(f"- **Explanation:** {r.explanation}")
            if r.source_title:
                lines.append(f"- **Matched Source:** {r.source_title}")
            if r.source_excerpt:
                lines.append(f"- **Source Excerpt:** {r.source_excerpt}")
            if r.source_url:
                lines.append(f"- **Source URL:** {r.source_url}")
            lines.append("")

    lines.extend([
        "---",
        f"*{report.disclaimer}*",
        "",
    ])
    return "\n".join(lines)

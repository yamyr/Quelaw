"""Report assembly: summary statistics and an overall risk level."""
from __future__ import annotations

import json
import re

from pydantic import JsonValue

from . import config
from .schema import (
    DISCLAIMER, NOT_FOUND, REQUIRES_REVIEW, UNCERTAIN, VERIFIED,
    Report, VerificationResult,
)


def build_report(
    results: list[VerificationResult], *, draft_sha256: str = "",
    dataset_fingerprint: str = "",
) -> Report:
    for result in results:
        reasons = list(result.review_reasons)
        if result.status != VERIFIED or (result.manual_review_required and not reasons):
            reasons.append(result.explanation)
        if result.quote_evidence and result.quote_evidence.status != "match_in_available_text":
            reasons.append(result.quote_evidence.reason)
        if result.fallback_reason:
            reasons.append(result.fallback_reason)
        result.review_reasons = tuple(dict.fromkeys(reasons))
    summary = {
        "total": len(results),
        "distinct_authorities": len({r.authority_key for r in results}),
        "verified": sum(r.status == VERIFIED for r in results),
        "not_found": sum(r.status == NOT_FOUND for r in results),
        "uncertain": sum(r.status == UNCERTAIN for r in results),
        "requires_review": sum(r.status == REQUIRES_REVIEW for r in results),
        "reviewed_occurrences": sum(bool(r.review_reasons) for r in results),
    }
    if not results:
        level, detail = "Unknown", "No legal authorities were detected in the draft."
    elif summary["not_found"]:
        level, detail = "High", "One or more authorities were not found in the dataset. Review against official sources."
    elif summary["reviewed_occurrences"]:
        level, detail = "Medium", "Some authority or quotation evidence needs manual review."
    else:
        level, detail = "Low", "All detected authorities meet the available dataset checks. Confirm official sources before use."
    verifiers = {result.verifier for result in results}
    mode = next(iter(verifiers)) if len(verifiers) == 1 else "mixed" if verifiers else "heuristic"
    return Report(
        draft_sha256=draft_sha256, dataset_fingerprint=dataset_fingerprint,
        verifier={"mode": mode, "model": config.ANTHROPIC_MODEL if "claude" in verifiers else None},
        summary=summary, results=results, risk_level=level, risk_detail=detail,
        disclaimer=DISCLAIMER,
    )


def report_to_markdown(report: Report) -> str:
    """Format a verification report as a structured Markdown document."""
    lines = [
        "# Quelaw Evidence Review", "",
        f"**Overall Risk:** {report.risk_level} — {report.risk_detail}", "",
        f"- Report schema: {report.schema_version}",
        f"- Draft SHA-256: {report.draft_sha256}",
        f"- Dataset fingerprint: {report.dataset_fingerprint}",
        f"- Verifier: {json.dumps(report.verifier, ensure_ascii=False)}", "",
        "## Summary", "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in report.summary.items())
    lines.extend(["", "## Findings", ""])
    if not report.results:
        lines.append("No legal authorities were detected in the draft.")
    for index, result in enumerate(report.results, 1):
        lines.extend([f"### {index}. Occurrence {result.occurrence_id}", ""])
        fields = result.to_dict()
        for key, value in fields.items():
            if isinstance(value, (dict, list)):
                lines.extend([f"**{key}**", "", _json_block(value), ""])
            else:
                lines.append(f"- **{key}:** {_literal_json(value)}")
        lines.append("")
    lines.extend(["---", report.disclaimer, ""])
    return "\n".join(lines)


def _json_block(value: JsonValue) -> str:
    serialized = json.dumps(value, ensure_ascii=False, indent=2)
    return f"```json\n{serialized}\n```"


def _literal_json(value: str | int | float | bool | None) -> str:
    serialized = json.dumps(value, ensure_ascii=False)
    delimiter = "`" * (1 + max((len(run.group()) for run in re.finditer(r"`+", serialized)), default=0))
    return f"{delimiter}{serialized}{delimiter}"

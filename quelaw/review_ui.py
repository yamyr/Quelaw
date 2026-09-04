from __future__ import annotations

import json
from collections.abc import Sequence

import streamlit as st

from .annotator import annotate_draft_html
from .corrections import OverlappingCorrectionsError, StaleCorrectionError, apply_corrections
from .report import report_to_markdown
from .schema import CorrectionProposal, Report, STATUS_LABEL, VerificationResult


def _apply(proposals: Sequence[CorrectionProposal]) -> None:
    try:
        st.session_state["draft"] = apply_corrections(st.session_state["draft"], proposals)
    except (StaleCorrectionError, OverlappingCorrectionsError) as error:
        st.session_state["correction_notice"] = f"Correction not applied: {error}. Check the current draft again."
    else:
        st.session_state["correction_notice"] = "Correction applied. Check the revised draft to refresh its evidence."
        st.session_state.pop("report", None)


def _source(result: VerificationResult) -> None:
    st.subheader("Available source evidence")
    if not result.source_id:
        st.info("No source selected from the dataset.")
        return
    st.text(result.source_title or result.source_id)
    st.caption(f"Source ID: {result.source_id}")
    if result.source_excerpt:
        st.text(result.source_excerpt)
    provenance = result.source_provenance
    if provenance is None:
        st.warning("Source provenance is unavailable. Review against an official source.")
        return
    st.write(f"Text fidelity: **{provenance.text_kind}** · Coverage: **{provenance.coverage}**")
    if result.source_url:
        st.link_button("Open official source", result.source_url)
    else:
        st.caption("Official URL: unknown")
    st.caption(f"Retrieved on: {provenance.retrieved_on or 'unknown'} · Version: {provenance.version_label or 'unknown'}")
    st.caption(f"Reuse status: {provenance.reuse_status} · Basis: {provenance.reuse_basis or 'unknown'}")
    for limitation in provenance.limitations:
        st.text(limitation)


def _finding(result: VerificationResult, index: int) -> None:
    st.subheader(f"Occurrence {index + 1}")
    st.text(result.citation)
    st.write(f"**{STATUS_LABEL[result.status]}** · Confidence {result.confidence:.0%}")
    st.caption(f"Finding {result.occurrence_id} · {result.type} · Characters {result.start_char}–{result.end_char}")
    st.text(result.explanation)
    if result.context_sentence:
        st.caption("Occurrence context")
        st.text(result.context_sentence)
    st.caption(f"Verifier: {result.verifier}")
    if result.review_reasons:
        st.write("**Review reasons**")
        for reason in result.review_reasons:
            st.warning(reason)
    _source(result)
    if result.quote_evidence:
        st.subheader("Quotation evidence")
        st.text(result.quote_text or "")
        st.write(f"Assessment: **{result.quote_evidence.status}**")
        st.text(result.quote_evidence.reason)
        if result.quote_evidence.matched_text:
            st.caption("Matched available text")
            st.text(result.quote_evidence.matched_text)
    if result.correction:
        st.subheader("Replacement preview")
        st.caption("Replace this occurrence")
        st.text(result.correction.expected_text)
        st.caption("With")
        st.text(result.correction.replacement)
        st.button(
            "Apply correction to this occurrence", key=f"fix_btn_{index}",
            on_click=_apply, args=((result.correction,),), width="stretch",
        )
    if result.external_search_url:
        portal = "eLitigation" if result.type == "case" else "Singapore Statutes Online"
        st.link_button(f"Search on {portal}", result.external_search_url, width="stretch")


def render_report(report: Report, current_draft: str) -> None:
    st.subheader("Summary")
    message = f"Overall risk: {report.risk_level} — {report.risk_detail}"
    if report.risk_level == "High":
        st.error(message)
    elif report.risk_level == "Medium":
        st.warning(message)
    elif report.risk_level == "Low":
        st.success(message)
    else:
        st.info(message)
    metrics = (
        ("Occurrences", "total"), ("Distinct authorities", "distinct_authorities"),
        ("Verified", "verified"), ("Not found", "not_found"),
        ("Uncertain", "uncertain"), ("Needs review", "requires_review"),
    )
    for column, (label, key) in zip(st.columns(len(metrics)), metrics, strict=True):
        column.metric(label, report.summary[key])
    st.caption(
        f"{report.summary['reviewed_occurrences']} occurrence(s) need review of authority or quotation evidence. "
        "Dataset matches do not establish legal authenticity, applicability or current law."
    )
    review, inventory = st.tabs(["Evidence review", "All findings"])
    with review:
        if report.results:
            selected = st.selectbox(
                "Select citation occurrence", range(len(report.results)),
                format_func=lambda i: f"{i + 1}. {report.results[i].citation}",
                key=f"finding_{report.draft_sha256}",
            )
            draft_column, evidence_column = st.columns([1, 1])
            with draft_column:
                st.subheader("Annotated draft")
                st.markdown(annotate_draft_html(current_draft, report.results), unsafe_allow_html=True)
            with evidence_column:
                with st.container(border=True):
                    _finding(report.results[selected], selected)
        else:
            st.info("No legal authorities were detected in the draft.")
        proposals = [result.correction for result in report.results if result.correction]
        if proposals:
            st.caption(f"Apply all {len(proposals)} proposed replacement(s), after reviewing their previews by occurrence.")
            st.button(
                "Apply all corrections", key="apply_all_fixes_btn",
                on_click=_apply, args=(proposals,),
            )
    with inventory:
        for index, result in enumerate(report.results, 1):
            st.write(f"**{index}. {STATUS_LABEL[result.status]}**")
            st.text(result.citation)
            st.caption(f"Finding {result.occurrence_id} · Source: {result.source_id or 'none'}")
    with st.expander("Report identity"):
        st.write(f"Schema version: {report.schema_version} · Verifier: {report.verifier['mode']}")
        st.caption("Draft SHA-256")
        st.code(report.draft_sha256, language=None)
        st.caption("Dataset fingerprint")
        st.code(report.dataset_fingerprint, language=None)
    st.divider()
    markdown_column, json_column = st.columns(2)
    markdown_column.download_button(
        "Download report (Markdown)", data=report_to_markdown(report),
        file_name="quelaw_report.md", mime="text/markdown", width="stretch",
    )
    json_column.download_button(
        "Download report (JSON)", data=json.dumps(report.to_dict(), indent=2),
        file_name="quelaw_report.json", mime="application/json", width="stretch",
    )

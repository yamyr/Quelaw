"""QueLaw — Streamlit frontend.

    streamlit run app.py

Paste an AI-generated legal draft, click "Check Draft", and review a verification
report grounded in the local Micro-LawNet sandbox.
"""
from __future__ import annotations

import streamlit as st

from quelaw import config, vectorstore
from quelaw.pipeline import check_draft
from quelaw.schema import (
    DISCLAIMER,
    NOT_FOUND,
    REQUIRES_REVIEW,
    STATUS_ICON,
    STATUS_LABEL,
    UNCERTAIN,
    VERIFIED,
)
from quelaw.sandbox import documents_cached

st.set_page_config(page_title="QueLaw — SG Legal Citation Checker", page_icon="⚖️", layout="wide")

_RISK_COLOR = {"High": "#c0392b", "Medium": "#d68910", "Low": "#1e8449", "Unknown": "#566573"}
_STATUS_COLOR = {
    VERIFIED: "#1e8449",
    NOT_FOUND: "#c0392b",
    UNCERTAIN: "#d68910",
    REQUIRES_REVIEW: "#2471a3",
}


def _load_demo() -> str:
    path = config.DEMO_DIR / "golden_path.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_upload(uploaded) -> str:
    name = uploaded.name.lower()
    if name.endswith(".txt"):
        return uploaded.read().decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        try:
            import io

            from docx import Document

            doc = Document(io.BytesIO(uploaded.read()))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            st.warning(f"Could not read .docx ({e}). Paste the text instead.")
    return ""


# --- Sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("QueLaw")
    st.caption("Singapore legal citation hallucination checker")

    index_count = vectorstore.count()
    sandbox_docs = len(documents_cached())
    st.metric("Sandbox documents", sandbox_docs)
    st.metric("Indexed chunks", index_count)

    if config.llm_enabled():
        st.success(f"Claude verification ON ({config.ANTHROPIC_MODEL})")
    else:
        st.info("Offline heuristic mode\n(set ANTHROPIC_API_KEY to enable Claude)")

    if st.button("🔁 Rebuild index", use_container_width=True):
        with st.spinner("Ingesting sandbox… (first run downloads the embedding model)"):
            n = vectorstore.ingest(reset=True)
        st.success(f"Indexed {n} chunks.")
        st.rerun()

    st.divider()
    st.caption(
        "Micro-LawNet is a small, controlled proof-of-concept dataset. Entries are "
        "paraphrased/placeholder, not authoritative legal text."
    )


# --- Main -----------------------------------------------------------------
st.title("⚖️ QueLaw")
st.markdown(
    "Paste an AI-generated legal draft. QueLaw extracts the legal authorities it "
    "cites and checks whether each one appears in a trusted Singapore legal dataset."
)

if vectorstore.count() == 0:
    st.warning(
        "The vector index is empty. Click **Rebuild index** in the sidebar (or run "
        "`py -3.12 scripts/ingest.py`). The heuristic verifier still works without it."
    )

col_a, col_b = st.columns([3, 1])
with col_b:
    st.write("")
    st.write("")
    if st.button("📄 Load demo draft", use_container_width=True):
        st.session_state["draft"] = _load_demo()
    uploaded = st.file_uploader("Or upload .txt / .docx", type=["txt", "docx"])
    if uploaded is not None:
        st.session_state["draft"] = _read_upload(uploaded)

with col_a:
    draft = st.text_area(
        "Legal draft",
        value=st.session_state.get("draft", ""),
        height=260,
        placeholder="Paste the AI-generated legal draft here…",
    )

check = st.button("🔍 Check Draft", type="primary")

if check:
    if not draft.strip():
        st.error("Please paste a draft or load the demo first.")
        st.stop()

    with st.spinner("Extracting citations and checking against the sandbox…"):
        report, _ = check_draft(draft)

    # Summary
    st.subheader("Summary")
    risk_color = _RISK_COLOR.get(report.risk_level, "#566573")
    st.markdown(
        f"<div style='padding:0.75rem 1rem;border-radius:8px;background:{risk_color};"
        f"color:white;font-weight:600;'>Overall risk: {report.risk_level} — "
        f"{report.risk_detail}</div>",
        unsafe_allow_html=True,
    )
    s = report.summary
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", s["total"])
    m2.metric("Verified", s["verified"])
    m3.metric("Not found", s["not_found"])
    m4.metric("Uncertain", s["uncertain"])
    m5.metric("Needs review", s["requires_review"])

    # Per-citation results
    st.subheader("Citations")
    if not report.results:
        st.info("No legal authorities were detected in the draft.")
    for r in report.results:
        color = _STATUS_COLOR.get(r.status, "#566573")
        icon = STATUS_ICON.get(r.status, "•")
        label = STATUS_LABEL.get(r.status, r.status)
        with st.container(border=True):
            head, badge = st.columns([4, 1])
            head.markdown(f"**{r.citation}**  \n<small>type: {r.type}</small>", unsafe_allow_html=True)
            badge.markdown(
                f"<div style='text-align:right;color:{color};font-weight:600;'>"
                f"{icon} {label}<br><small>confidence {r.confidence:.0%}</small></div>",
                unsafe_allow_html=True,
            )
            st.write(r.explanation)
            if r.source_title:
                st.caption(f"Matched source: {r.source_title}")
            if r.source_excerpt:
                st.markdown(
                    f"<div style='font-size:0.85rem;color:#444;border-left:3px solid "
                    f"{color};padding-left:0.6rem;'>{r.source_excerpt}</div>",
                    unsafe_allow_html=True,
                )
            if r.source_url:
                st.caption(r.source_url)

    # Export
    st.download_button(
        "⬇️ Download report (JSON)",
        data=__import__("json").dumps(report.to_dict(), indent=2),
        file_name="quelaw_report.json",
        mime="application/json",
    )

st.divider()
st.caption(DISCLAIMER)

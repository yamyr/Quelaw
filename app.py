"""Quelaw — Streamlit frontend.

    uv run streamlit run app.py

Paste an AI-generated legal draft, click "Check Draft", and review a verification
report grounded in the local Micro-LawNet sandbox.

Demo mode (sidebar toggle) swaps the free-text box for a picker of curated
scenarios and forces the offline heuristic verifier, so a live demo is fully
deterministic and needs no API key, no internet, and no pre-built index.
"""
from __future__ import annotations

import html

import streamlit as st

from quelaw import config, demo, vectorstore
from quelaw.pipeline import check_draft
from quelaw.report import report_to_markdown
from quelaw.sandbox import documents_cached
from quelaw.schema import (
    DISCLAIMER,
    NOT_FOUND,
    REQUIRES_REVIEW,
    STATUS_ICON,
    STATUS_LABEL,
    UNCERTAIN,
    VERIFIED,
)

st.set_page_config(page_title="Quelaw — SG Legal Citation Checker", page_icon="⚖️", layout="wide")

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


from quelaw.annotator import annotate_draft_html, apply_all_fixes, apply_fix


def _set_draft(draft: str) -> None:
    st.session_state["draft"] = draft


def _render_report(report, current_draft: str = "") -> None:
    """Render a verification report: summary, annotated draft, per-citation cards, export."""
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

    st.caption(
        "Quelaw never labels a case "
        '"fake" or "good law". It shows what it could and could not match in the '
        "trusted dataset and points you to the source so you can decide."
    )

    tab_annotated, tab_cards = st.tabs(["📝 Annotated Draft", "📋 Citation Analysis"])

    with tab_annotated:
        fixable = [r for r in report.results if r.suggested_fix]
        if fixable:
            st.info(f"💡 Found {len(fixable)} suggested correction(s) for transcription mismatches.")
            st.button(
                "✨ Apply All Fixes to Draft", key="apply_all_fixes_btn", type="primary",
                on_click=_set_draft, args=(apply_all_fixes(current_draft, report.results),),
            )

        st.markdown(annotate_draft_html(current_draft, report.results), unsafe_allow_html=True)

    with tab_cards:
        if not report.results:
            st.info("No legal authorities were detected in the draft.")
        for idx, r in enumerate(report.results):
            color = _STATUS_COLOR.get(r.status, "#566573")
            icon = STATUS_ICON.get(r.status, "•")
            label = STATUS_LABEL.get(r.status, r.status)
            with st.container(border=True):
                head, badge = st.columns([3, 2])
                head.markdown(
                    f"**{html.escape(r.citation)}**  \n<small>type: `{html.escape(r.type)}`</small>", unsafe_allow_html=True
                )
                badge.markdown(
                    f"<div style='text-align:right;color:{color};font-weight:600;'>"
                    f"{icon} {label}<br><small>confidence {r.confidence:.0%}</small></div>",
                    unsafe_allow_html=True,
                )
                st.write(r.explanation)

                if r.quote_text:
                    if r.quote_status == "verified":
                        st.info(f'💬 Nearby quotation matches sandbox text: *"{r.quote_text}"*')
                    elif r.quote_status == "not_found":
                        st.warning(f'⚠️ Nearby quotation was not matched in available sandbox text: *"{r.quote_text}"*')
                    st.caption("Experimental text comparison only. Sandbox text may be paraphrased or incomplete; verify quotations against the official source.")

                if r.source_title:
                    st.caption(f"Matched source: {r.source_title}")
                if r.source_excerpt:
                    st.markdown(
                        f"<div style='font-size:0.85rem;color:#444;border-left:3px solid "
                        f"{color};padding-left:0.6rem;margin-bottom:0.5rem;'>{html.escape(r.source_excerpt)}</div>",
                        unsafe_allow_html=True,
                    )
                if r.source_url:
                    st.caption(r.source_url)

                action_col1, action_col2 = st.columns([1, 1])
                with action_col1:
                    if r.suggested_fix:
                        st.button(
                            f"💡 Quick Fix: Replace with '{r.suggested_fix}'", key=f"fix_btn_{idx}",
                            on_click=_set_draft,
                            args=(apply_fix(current_draft, r.citation, r.suggested_fix),),
                        )
                with action_col2:
                    if r.external_search_url:
                        portal_name = "eLitigation" if r.type == "case" else "Singapore Statutes Online"
                        st.link_button(f"🔎 Search on {portal_name}", r.external_search_url, width="stretch")

                if r.status == NOT_FOUND:
                    st.caption(
                        "⚖️ Not in the dataset — verify against official sources "
                        "(eLitigation / Singapore Statutes Online) before relying on it."
                    )
                elif r.status in (UNCERTAIN, REQUIRES_REVIEW):
                    st.caption("⚖️ Quelaw can't fully confirm this — read the source above and decide.")

    st.divider()
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ Download report (Markdown)",
            data=report_to_markdown(report),
            file_name="quelaw_report.md",
            mime="text/markdown",
            width="stretch",
        )
    with d2:
        st.download_button(
            "⬇️ Download report (JSON)",
            data=__import__("json").dumps(report.to_dict(), indent=2),
            file_name="quelaw_report.json",
            mime="application/json",
            width="stretch",
        )


# --- Sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("Quelaw")
    st.caption("Singapore legal citation hallucination checker")

    demo_mode = st.toggle(
        "🎬 Demo mode",
        value=False,
        help="Curated scenarios, fully offline and deterministic — for live demos. "
        "Bypasses Claude so the result is identical every time.",
    )

    index_count = vectorstore.count()
    sandbox_docs = len(documents_cached())
    st.metric("Sandbox documents", sandbox_docs)
    st.metric("Indexed chunks", index_count)

    if demo_mode:
        st.success("Demo mode ON — offline heuristic, deterministic output")
    elif config.llm_enabled():
        st.success(f"Claude verification ON ({config.ANTHROPIC_MODEL})")
    else:
        st.info("Offline heuristic mode\n(set ANTHROPIC_API_KEY to enable Claude)")

    if st.button("🔁 Rebuild index", width="stretch"):
        with st.spinner("Ingesting sandbox… (first run downloads the embedding model)"):
            n = vectorstore.ingest(reset=True)
        st.success(f"Indexed {n} chunks.")
        st.rerun()

    st.divider()
    st.caption(
        "Micro-LawNet is a small, controlled proof-of-concept dataset. Entries are "
        "paraphrased/placeholder, not authoritative legal text."
    )

    st.divider()
    st.caption("☁️ Run Quelaw locally or deploy it on Streamlit Community Cloud.")


# --- Main -----------------------------------------------------------------
st.title("⚖️ Quelaw")
st.markdown(
    "Paste an AI-generated legal draft. Quelaw extracts the legal authorities it "
    "cites and checks whether each one appears in a trusted Singapore legal dataset."
)

run_now = False  # set when a demo scenario's Run button is pressed

if demo_mode:
    st.info(
        "🎬 **Demo mode** — runs fully offline on the controlled sandbox: no API "
        "key, no internet, no pre-built index, identical result every time. Pick a "
        "scenario, then **Run**."
    )
    titles = [sc.title for sc in demo.SCENARIOS]
    choice = st.selectbox("Demo scenario", titles, key="demo_choice")
    scenario = demo.by_title(choice)

    # Load the scenario draft into the editor whenever the selection changes,
    # without clobbering manual edits on every rerun.
    if st.session_state.get("demo_scenario_id") != scenario.id:
        st.session_state["demo_scenario_id"] = scenario.id
        st.session_state["draft"] = scenario.draft

    st.caption(f"ℹ️ {scenario.tagline}")
    with st.expander("🗣️ Talking point (what to say while it runs)"):
        st.write(scenario.talking_point)
else:
    if vectorstore.count() == 0:
        st.warning(
            "The vector index is empty. Click **Rebuild index** in the sidebar (or run "
            "`uv run python scripts/ingest.py`). The heuristic verifier still works without it."
        )

    col_a, col_b = st.columns([3, 1])
    with col_b:
        st.write("")
        st.write("")
        if st.button("📄 Load demo draft", width="stretch"):
            st.session_state["draft"] = _load_demo()
        uploaded = st.file_uploader("Or upload .txt / .docx", type=["txt", "docx"])
        if uploaded is not None and st.session_state.get("loaded_upload_id") != uploaded.file_id:
            st.session_state["draft"] = _read_upload(uploaded)
            st.session_state["loaded_upload_id"] = uploaded.file_id

draft = st.text_area(
    "Legal draft",
    key="draft",
    height=260,
    placeholder="Paste the AI-generated legal draft here…",
)

check_label = "▶️ Run scenario" if demo_mode else "🔍 Check Draft"
check = st.button(check_label, type="primary")

if check:
    if not draft.strip():
        st.error("Please paste a draft or load a scenario first.")
        st.stop()

    spinner_msg = (
        "Running the offline checker on the sandbox…"
        if demo_mode
        else "Extracting citations and checking against the sandbox…"
    )
    # Demo mode forces the deterministic offline verifier (use_llm=False);
    # normal mode lets config decide (use_llm=None).
    use_llm = False if demo_mode else None
    with st.spinner(spinner_msg):
        report, _ = check_draft(draft, use_llm=use_llm)
        st.session_state["report"] = report
        st.session_state["reported_draft"] = draft

if "report" in st.session_state and st.session_state.get("reported_draft") == draft:
    _render_report(st.session_state["report"], current_draft=draft)

st.divider()
st.caption(DISCLAIMER)

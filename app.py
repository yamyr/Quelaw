"""Quelaw — Streamlit frontend.

    uv run streamlit run app.py

Paste an AI-generated legal draft, click "Check Draft", and review a verification
report grounded in the local Micro-LawNet sandbox.

Demo mode (sidebar toggle) swaps the free-text box for a picker of curated
scenarios and forces the offline heuristic verifier, so a live demo is fully
deterministic and needs no API key, no internet, and no pre-built index.
"""
from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile

from docx import Document
from lxml.etree import XMLSyntaxError
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from quelaw import config, demo, vectorstore
from quelaw.pipeline import check_draft
from quelaw.provenance import DatasetValidationError, load_dataset
from quelaw.review_ui import render_report
from quelaw.schema import DISCLAIMER

st.set_page_config(page_title="Quelaw — SG Legal Citation Checker", page_icon="⚖️", layout="wide")

def _load_demo() -> str:
    path = config.DEMO_DIR / "golden_path.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_upload(uploaded: UploadedFile) -> str:
    name = uploaded.name.lower()
    if name.endswith(".txt"):
        try:
            text = uploaded.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Save the text file as UTF-8 and upload it again.") from error
    elif name.endswith(".docx"):
        try:
            doc = Document(BytesIO(uploaded.getvalue()))
            text = "\n".join(p.text for p in doc.paragraphs)
        except (BadZipFile, KeyError, ValueError, XMLSyntaxError) as error:
            raise ValueError("Could not read this Word document. Upload a valid .docx or paste the text.") from error
    else:
        raise ValueError("Upload a .txt or .docx file.")
    if not text.strip():
        raise ValueError("No readable draft text was found. Paste the text or choose another file.")
    return text


def _switch_demo_mode() -> None:
    for key in ("draft", "report", "reported_draft"):
        saved_key = f"normal_{key}"
        if st.session_state["demo_mode"]:
            if key in st.session_state:
                st.session_state[saved_key] = st.session_state.pop(key)
        else:
            st.session_state.pop(key, None)
            if saved_key in st.session_state:
                st.session_state[key] = st.session_state.pop(saved_key)
    st.session_state.pop("demo_scenario_id", None)
    st.session_state.pop("correction_notice", None)


try:
    dataset = load_dataset(config.SANDBOX_DIR)
except DatasetValidationError as error:
    st.error(f"Sandbox validation failed: {error}")
    st.stop()


# --- Sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("Quelaw")
    st.caption("Singapore legal citation hallucination checker")

    demo_mode = st.toggle(
        "🎬 Demo mode",
        value=False,
        key="demo_mode",
        on_change=_switch_demo_mode,
        help="Curated scenarios, fully offline and deterministic — for live demos. "
        "Bypasses Claude so the result is identical every time. "
        "Your normal draft and report are restored when you turn this off.",
    )

    index_state = vectorstore.index_status(dataset)
    index_count = vectorstore.count()
    sandbox_docs = len(dataset.records)
    st.metric("Sandbox documents", sandbox_docs)
    st.metric("Indexed chunks", index_count)

    if index_state == "stale":
        st.warning("Index rebuild required: the saved index does not match the current dataset. Offline checks remain available.")

    if demo_mode:
        st.success("Demo mode ON — offline heuristic, deterministic output")
    elif config.llm_enabled():
        st.success(f"Claude verification ON ({config.ANTHROPIC_MODEL})")
    else:
        st.info("Offline heuristic mode\n(set ANTHROPIC_API_KEY to enable Claude)")

    if st.button("🔁 Rebuild index", width="stretch"):
        with st.spinner("Ingesting sandbox… (first run downloads the embedding model)"):
            n = vectorstore.ingest(reset=True, dataset=dataset)
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
    if index_state == "missing":
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
        if uploaded is None:
            st.session_state.pop("upload_error", None)
        if uploaded is not None and st.session_state.get("loaded_upload_id") != uploaded.file_id:
            try:
                uploaded_draft = _read_upload(uploaded)
            except ValueError as error:
                st.session_state["upload_error"] = str(error)
            else:
                st.session_state["draft"] = uploaded_draft
                st.session_state.pop("upload_error", None)
            st.session_state["loaded_upload_id"] = uploaded.file_id
        if "upload_error" in st.session_state:
            st.warning(f"{st.session_state['upload_error']} Your draft is unchanged.")

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
        report, _ = check_draft(draft, use_llm=use_llm, dataset=dataset)
        st.session_state["report"] = report
        st.session_state["reported_draft"] = draft

if "correction_notice" in st.session_state:
    st.info(st.session_state.pop("correction_notice"))

if "report" in st.session_state:
    saved_report = st.session_state["report"]
    if st.session_state.get("reported_draft") != draft:
        st.info("Draft changed. Check it again to refresh the report.")
    elif saved_report.dataset_fingerprint != dataset.fingerprint:
        st.warning("Dataset changed. Check the draft again against the current sources.")
    else:
        render_report(saved_report, current_draft=draft)

st.divider()
st.caption(DISCLAIMER)

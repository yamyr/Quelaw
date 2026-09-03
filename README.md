# Quelaw

[![CI](https://github.com/yamyr/Quelaw/actions/workflows/ci.yml/badge.svg)](https://github.com/yamyr/Quelaw/actions/workflows/ci.yml)
&nbsp;[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
&nbsp;[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

> **Repository:** [github.com/yamyr/Quelaw](https://github.com/yamyr/Quelaw)

Quelaw checks whether legal authorities cited in an AI-generated draft match a small, controlled Singapore legal dataset called **Micro-LawNet**. Paste a draft or upload a `.txt` or `.docx` file to review its cases, statutes, and rules.

This is a proof-of-concept citation checker. The sandbox contains paraphrased and placeholder material; a match establishes coverage in that dataset, not the validity of a legal argument or an authority's current legal status.

> **Disclaimer.** Quelaw is a legal verification support tool. It does not provide legal advice and does not replace professional legal judgment. Review flagged items against official legal sources such as [eLitigation](https://www.elitigation.sg/) and [Singapore Statutes Online](https://sso.agc.gov.sg/) before use.

## How it works

```text
Draft → extract citations → match sandbox authorities → verification report
                           ↳ optional ChromaDB retrieval + Claude verification
```

- **Extraction:** regular expressions recognize SG citations such as `[2007] SGCA 37`, `section 14 of the Civil Law Act`, and `Order 9 Rule 6`. Claude can optionally supplement extraction.
- **Verification:** a deterministic heuristic compares references with the sandbox JSON. The optional Claude path uses candidate sources retrieved from a local ChromaDB index and falls back to the heuristic if the API call fails.
- **Review:** a summary and risk level lead to an annotated draft and per-citation analysis. Cards show available source excerpts, quote-match hints, suggested corrections, and links for searching official sources.
- **Corrections and export:** apply an individual suggestion or all suggestions, then check the edited draft again. Download the report as Markdown or JSON. JSON includes the detailed result fields; the Markdown report is a summary of citation findings and sources.

Quote-match hints are experimental comparisons against the sandbox text, which may be paraphrased or incomplete. They do not authenticate quotations against official judgments. Corrections are suggestions to review before applying.

| Status | Meaning |
|---|---|
| ✅ Verified in dataset | A sandbox entry matches the authority |
| ❌ Not found in dataset | No match; the authority may be outside the sandbox or hallucinated |
| ⚠️ Uncertain match | A similar authority was found, with a possible citation or name mismatch |
| 🔎 Requires manual review | The authority or provision could only be partly confirmed |

Quelaw uses these labels rather than declaring an authority "fake" or "good law."

## Quick start

Use **Python 3.14** and [install uv](https://docs.astral.sh/uv/getting-started/installation/). Run these commands from a terminal:

```bash
git clone https://github.com/yamyr/Quelaw.git
cd Quelaw
uv sync --locked
uv run --locked streamlit run app.py
```

The first setup requires internet access to obtain dependencies and, if needed, Python. `uv sync --locked` creates `.venv` from the committed lockfile and includes the development tools. No manual activation is needed when using `uv run`.

In the app, turn on **🎬 Demo mode**, choose a scenario, and click **▶️ Run scenario**. Demo verification runs offline after setup, with no API key, embedding download, or pre-built index. The draft remains editable.

For a free-text example, click **📄 Load demo draft**, then **🔍 Check Draft**. This memo includes `Spandeck … [2007] SGCA 37`, the planted example `Tan Ah Kow v Singapore Airlines [2025] SGHC 999`, a statute, and a rule.

### Optional Claude verification

Copy `.env.example` to `.env` (`cp .env.example .env` on macOS/Linux; `copy .env.example .env` on Windows). Set `ANTHROPIC_API_KEY`; optionally set `ANTHROPIC_MODEL` to override the configured default. Restart the app after changing configuration.

Build the retrieval index before using Claude:

```bash
uv run --locked python scripts/ingest.py
```

The first ingestion downloads the embedding model. ChromaDB stores the resulting index locally in `chroma/`; the sidebar **🔁 Rebuild index** button performs the same rebuild. With Claude enabled, extraction can send draft text to the API and verification sends citation and retrieved-source context. Demo mode bypasses Claude even when a key is configured.

### pip installation fallback

For environments that consume `requirements.txt`, including deployment setups using pip, create and activate a Python 3.14 virtual environment and run:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

`requirements.txt` is a generated runtime dependency export. Use the uv workflow for development and tests; see [Contributing](CONTRIBUTING.md) for dependency changes.

## Demo mode

The sidebar scenario picker loads a curated draft into the editor. Each scenario carries a talking point for the presenter and expected outcomes checked by the test suite.

| Scenario | Shows | Risk |
|---|---|---|
| 🎯 Hallucinated case | A deliberately fabricated authority among matching citations | High |
| ✅ Clean draft | All detected authorities match the sandbox | Low |
| ⚠️ Right case, wrong citation | A transcription error flagged for review | Medium |
| 🧪 Mixed memo | All four verification outcomes | High |

Lead with **🎯 Hallucinated case** to demonstrate detection of the planted authority. Dead-link and overturned-ruling checks remain future work; see the [roadmap](ROADMAP.md).

Before presenting, run:

```bash
uv run --locked python scripts/check_demo_scenarios.py
uv run --locked python scripts/check_demo.py
```

The scenario checker explicitly forces the offline heuristic. The golden-path script follows configuration, so leave `ANTHROPIC_API_KEY` unset for a heuristic run.

## Share the offline demo

The verifier can run offline after dependencies are installed. Hosting, tunnels, and viewers connecting to a hosted app still require network access.

1. **A hosted link — Streamlit Community Cloud.** Follow the [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), choose repository `yamyr/Quelaw`, branch `main`, and entrypoint `app.py`, and select Python 3.14 in Advanced settings (the service default may differ). Leave `ANTHROPIC_API_KEY` unset and use demo mode. Community Cloud prioritizes `uv.lock` over `requirements.txt`; the generated requirements file remains available for pip-based deployment workflows. See its [dependency selection rules](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies). This repository provides deployment instructions, not an existing hosted demo URL.

2. **A temporary link during a call — a tunnel.** With the app running locally, use an installed tunnel tool:

   ```bash
   cloudflared tunnel --url http://localhost:8501
   # Alternatively: ngrok http 8501
   ```

   The link is public while the tunnel runs. Same-network viewers can also use the Network URL printed by Streamlit.

3. **Run it locally — teammates and developers.** Follow the quick start, then turn on demo mode. Install dependencies before going offline; no embedding model is needed for demo verification. If sharing a zip, exclude `.venv/`, `chroma/`, `.env`, and local secrets.

## Project layout

```text
app.py                        # Streamlit UI
pyproject.toml                # application metadata and dependency declarations
uv.lock                       # resolved development and runtime dependencies
requirements.txt              # generated runtime export for pip consumers
scripts/ingest.py             # build the ChromaDB vector store
scripts/check_demo.py         # golden-path smoke run
scripts/check_demo_scenarios.py # deterministic scenario checks
quelaw/
  extraction.py              # regex and optional Claude extraction
  verification.py            # heuristic and Claude result handling
  vectorstore.py             # ChromaDB ingest and retrieval
  sandbox.py                 # sandbox JSON loading
  annotator.py               # draft annotations and correction helpers
  llm.py                     # optional Claude API adapter
  report.py                  # summary, risk level, and Markdown export
  schema.py                  # result types and controlled vocabulary
  demo.py                    # curated scenarios and expected outcomes
data/sandbox/                # proof-of-concept cases, statutes, and rules
data/demo/                   # sample inputs and expected findings
tests/                       # pipeline, extraction, demo, and UI checks
docs/DESIGN.md               # current UI conventions
```

## Dataset and next steps

`data/sandbox/` contains a small set of Singapore authorities as JSON. Entries are **paraphrased or placeholder summaries with placeholder URLs**, not authoritative legal text. Search links open external portals for manual follow-up; Quelaw does not fetch those portals to verify results.

The next milestone focuses on source provenance, evaluation, and release readiness. The [roadmap](ROADMAP.md) separates current features from planned work. Live LawNet integration is a possible later path, not a current dependency.

## Tests and contributions

```bash
uv sync --locked
uv run --locked python -m pytest
uv run --locked python -m compileall -q app.py quelaw scripts
```

[CI](.github/workflows/ci.yml) installs the locked dependencies and runs checks including the deterministic scenarios and Streamlit AppTest coverage without Claude credentials. See [Contributing](CONTRIBUTING.md) for the development workflow and [UI design conventions](docs/DESIGN.md) for changes to the interface.

## References

- [Singapore eLitigation](https://www.elitigation.sg/) — official portal for manual case verification.
- [Singapore Statutes Online](https://sso.agc.gov.sg/) — official statute source for manual review.
- [Streamlit Community Cloud](https://share.streamlit.io/) — hosting option; see the [deployment documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app).
- [uv](https://docs.astral.sh/uv/) — dependency management; see [locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).
- [ChromaDB](https://docs.trychroma.com/) — local persistent vector store.
- [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — embedding model used by ChromaDB's default embedding function.

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).

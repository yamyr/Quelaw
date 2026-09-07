# Quelaw

[![CI](https://github.com/yamyr/Quelaw/actions/workflows/ci.yml/badge.svg)](https://github.com/yamyr/Quelaw/actions/workflows/ci.yml)
&nbsp;[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
&nbsp;[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

> **Repository:** [github.com/yamyr/Quelaw](https://github.com/yamyr/Quelaw)
> **Test app:** [quelaw-dev.streamlit.app](https://quelaw-dev.streamlit.app/) · offline verification · development branch

Quelaw checks whether legal authorities cited in an AI-generated draft match a small, controlled Singapore legal dataset called **Micro-LawNet**. Paste a draft or upload a `.txt` or `.docx` file to review its cases, statutes, and rules.

**0.2.0 is an untagged release candidate.** It adds source provenance, occurrence-specific review and corrections, report schema `2`, and a repeatable offline evaluation. Release review and demonstration are separate gates; see the [changelog](CHANGELOG.md) and [release procedure](CONTRIBUTING.md#release-demonstration).

This is a proof-of-concept citation checker. Its nine sandbox entries are paraphrased or synthetic summaries; a match establishes coverage in that dataset, not the validity of a legal argument or an authority's current legal status. The engineering evaluation awaits legal domain review and supports no legal accuracy claim.

> **Disclaimer.** Quelaw is a legal verification support tool. It does not provide legal advice and does not replace professional legal judgment. Review flagged items against official legal sources such as [eLitigation](https://www.elitigation.sg/) and [Singapore Statutes Online](https://sso.agc.gov.sg/) before use.

## How it works

```text
Draft → extract citations → match sandbox authorities → verification report
                           ↳ optional ChromaDB retrieval + Claude verification
```

- **Extraction:** regular expressions recognize SG citations such as `[2007] SGCA 37`, `section 14 of the Civil Law Act`, and `Order 9 Rule 6`. Each occurrence retains its draft offsets, including repeated references to the same authority. Claude can optionally supplement extraction with spans validated against the draft.
- **Verification:** a deterministic heuristic compares references with the validated sandbox. The optional Claude path binds each usable verdict to a retrieved local source ID; invalid responses fall back to the heuristic with a visible reason. An index built for a different dataset must be rebuilt before retrieval.
- **Review:** select a finding in the annotated draft/evidence workspace to inspect its occurrence, source identity, fidelity, coverage, quotation limits, and review reasons. Summaries distinguish citation occurrences from distinct authorities.
- **Corrections:** preview a replacement for one occurrence or apply the available proposals together. Proposals carry the reviewed draft hash and exact span; stale or overlapping proposals are rejected before any change. An edit invalidates the report and requires a new check.
- **Export:** Markdown and JSON carry the same material evidence. Report schema `2` includes the draft SHA-256, dataset fingerprint, verifier metadata, occurrence and distinct-authority counts, finding/source identities, review flags, quotation evidence, and correction proposals. Consumers of schema `1` must explicitly migrate.

Quotation states are `match_in_available_text`, `not_found_in_available_text`, `evidence_limited`, or `ambiguous_attribution`. An exact phrase in a paraphrase remains evidence-limited, and missing text in an excerpt or summary cannot establish absence from the full source. The bundled summaries cannot authenticate quotations against official judgments. Corrections remain suggestions for human review.

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

For day-to-day development on macOS/Linux, use `make setup`, then `make dev-offline`. Run `make check-fast` while iterating and `make check` before a pull request. `make upgrade` updates compatible packages and the runtime export. See the [development workflow](CONTRIBUTING.md#daily-development) for targeted tests, optional Claude mode, and portable commands.

In the app, turn on **🎬 Demo mode**, choose a scenario, and click **▶️ Run scenario**. Demo verification runs offline after setup, with no API key, embedding download, or pre-built index. The draft remains editable. Turning demo mode off restores your normal draft and report for the current session.

Uploads replace the editor only after the file is read successfully and contains text. Empty or unreadable files preserve your draft and report and show an error notice. Text files must use UTF-8 (with or without a byte-order mark). Word imports currently read body paragraphs; paste any text from tables, headers, footnotes, or text boxes that also needs checking.

For a free-text example, click **📄 Load demo draft**, then **🔍 Check Draft**. This memo includes `Spandeck … [2007] SGCA 37`, the planted example `Tan Ah Kow v Singapore Airlines [2025] SGHC 999`, a statute, and a rule.

### Optional Claude verification

Copy `.env.example` to `.env` (`cp .env.example .env` on macOS/Linux; `copy .env.example .env` on Windows). Set `ANTHROPIC_API_KEY`; optionally set `ANTHROPIC_MODEL` to override the configured default. Restart the app after changing configuration.

Build the retrieval index before using Claude:

```bash
uv run --locked python scripts/ingest.py
```

The first ingestion downloads the embedding model. ChromaDB stores the resulting index locally in `chroma/`; the sidebar **🔁 Rebuild index** button performs the same rebuild. Index metadata records the dataset fingerprint and source IDs. If the dataset changes, explicitly rebuild the index; offline checking remains usable. With Claude enabled, extraction can send draft text to the API and verification sends citation and retrieved-source context. Demo mode bypasses Claude even when a key is configured.

The locked ChromaDB version has four unresolved advisories. Read the [dependency security notes](CHANGELOG.md#unresolved-chromadb-advisories) before using retrieval or considering a server deployment.

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

Both commands explicitly force the offline heuristic, even when `ANTHROPIC_API_KEY` is configured.

## Share the offline demo

The verifier can run offline after dependencies are installed. Hosting, tunnels, and viewers connecting to a hosted app still require network access.

1. **A hosted link — Streamlit Community Cloud.** Follow the [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), choose repository `yamyr/Quelaw`, branch `main`, and entrypoint `app.py`, and select Python 3.14 in Advanced settings (the service default may differ). Leave `ANTHROPIC_API_KEY` unset and use demo mode. Community Cloud prioritizes `uv.lock` over `requirements.txt`; the generated requirements file remains available for pip-based deployment workflows. See its [dependency selection rules](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies). The persistent [test app](https://quelaw-dev.streamlit.app/) runs from `codex/development-workflow-refresh` with Python 3.14 and no Claude credentials. It updates when that branch changes; the existing `main` deployment is separate.

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
Makefile                     # shared setup, development and CI commands
scripts/check_demo.py         # always-offline golden-path smoke run
scripts/check_demo_scenarios.py # deterministic scenario checks
scripts/check_dataset.py      # validate source provenance and print its fingerprint
scripts/evaluate.py           # offline regression evaluation and baseline comparison
quelaw/
  extraction.py              # regex and optional Claude extraction
  verification.py            # heuristic and Claude result handling
  vectorstore.py             # ChromaDB ingest and retrieval
  sandbox.py                 # validated sandbox loading adapter
  provenance.py              # source inventory validation and dataset fingerprint
  evidence.py                # conservative quotation and Claude source evidence
  annotator.py               # draft annotations and correction helpers
  llm.py                     # optional Claude API adapter
  report.py                  # summary, risk level, and Markdown export
  schema.py                  # result types and controlled vocabulary
  demo.py                    # curated scenarios and expected outcomes
data/sandbox/                # nine proof-of-concept source summaries
data/demo/                   # sample inputs and expected findings
data/evaluation/v1/          # engineering cases, expectations, and baseline
tests/                       # pipeline, extraction, demo, and UI checks
docs/DESIGN.md               # current UI conventions
```

## Dataset and provenance

`data/sandbox/` contains nine validated JSON records. All have `coverage="summary"`: five case paraphrases and four synthetic fixtures. No record contains complete official text.

| Record | Text kind |
|---|---|
| Spandeck Engineering v Defence Science & Technology Agency, `[2007] SGCA 37` | Paraphrase |
| RDC Concrete v Sato Kogyo, `[2007] SGCA 39` | Paraphrase |
| ACB v Thomson Medical, `[2017] SGCA 20` | Paraphrase |
| Public Prosecutor v Lam Leng Hung, `[2018] SGCA 7` | Paraphrase |
| BOM v BOK, `[2018] SGCA 83` | Paraphrase |
| ABC v DEF, `[2023] SGHC 100` | Synthetic case fixture |
| Civil Law Act, section 14 | Synthetic provision placeholder |
| Penal Code, section 300 | Synthetic provision placeholder |
| Rules of Court 2021, Order 9 Rule 6 | Synthetic provision placeholder |

For every record, `official_url`, `retrieved_on`, `version_label`, and `reuse_basis` are null, and `reuse_status="unverified"`. Legacy dates and placeholder `source_url` strings do not establish retrieval, source currency, or reuse permission. The recorded limitations explain this. Search links open external portals for manual follow-up; Quelaw does not fetch those portals to verify results.

Run `uv run --locked python scripts/check_dataset.py` to validate the inventory and print its SHA-256 fingerprint. Changing validated source text or provenance changes that fingerprint; reordering JSON object keys does not. The candidate fingerprint is recorded in the [changelog](CHANGELOG.md). Live LawNet integration and broader official-source coverage remain [later work](ROADMAP.md).

## Offline evaluation

The versioned [evaluation corpus](data/evaluation/v1/README.md) contains at least 30 independently specified engineering fixtures. Cases cover extraction spans and parsed fields, authority outcomes, quotation limits, repeated references, correction safety, and malformed mocked Claude responses. Legal expectations carry `reviewer_status="legal_domain_review_pending"`; passing the baseline measures engineering consistency, not legal accuracy.

After installing dependencies, run:

```bash
uv run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json
```

The evaluation command runs without network or API access and needs no key, embedding download, or vector index. Its JSON summary separates extraction precision/recall and span accuracy from verification confusion counts and quotation outcomes. Material expectation differences cause a nonzero exit; an aggregate improvement cannot conceal a changed false verification. Baseline changes require review of the differing cases.

## Tests and contributions

```bash
make setup
make check
```

For faster feedback, use `make check-fast` or `make test TEST_ARGS="tests/test_extraction.py -x"`. The [Makefile](Makefile) lists the equivalent `uv` commands for environments without Make.

[CI](.github/workflows/ci.yml) uses the same full check target: locked dependencies, source validation, offline evaluation, tests, both demo commands, correctness lint, and runtime export drift. See [Contributing](CONTRIBUTING.md) for the development workflow and release demonstration, and [UI design conventions](docs/DESIGN.md) for interface changes.

## References

- [Singapore eLitigation](https://www.elitigation.sg/) — official portal for manual case verification.
- [Singapore Statutes Online](https://sso.agc.gov.sg/) — official statute source for manual review.
- [Streamlit Community Cloud](https://share.streamlit.io/) — hosting option; see the [deployment documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app).
- [uv](https://docs.astral.sh/uv/) — dependency management; see [locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).
- [ChromaDB](https://docs.trychroma.com/) — local persistent vector store.
- [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — embedding model used by ChromaDB's default embedding function.

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).

# QueLaw

A Singapore-focused tool that checks whether the legal authorities cited in an AI-generated draft actually exist in a trusted Singapore legal dataset.

QueLaw is a **legal citation hallucination checker**, not a legal-research engine or an AI lawyer. You paste an AI-generated legal draft; it extracts the cited authorities (cases, statutes, rules) and returns a verification report grounded — via Retrieval-Augmented Generation — in a small, controlled Singapore legal sandbox ("Micro-LawNet").

> **Disclaimer.** QueLaw is a legal verification *support* tool. It does not provide legal advice and does not replace professional legal judgment. All flagged items should be manually reviewed against official legal sources (e.g. [eLitigation](https://www.elitigation.sg/), [Singapore Statutes Online](https://sso.agc.gov.sg/)) before use.

## How it works

```
Paste draft → extract citations → retrieve from sandbox → verify (RAG) → report
```

- **Extraction** — regex for well-formed SG citations (`[2007] SGCA 37`, `section 14 of the Civil Law Act`, `Order 9 Rule 6`), with an optional Claude fallback for less standard references.
- **Retrieval** — the sandbox is embedded into a local on-disk **ChromaDB** (built-in MiniLM embeddings; downloaded once, then offline).
- **Verification** — each citation is checked against the retrieved sources. With a Claude key it uses an LLM grounded in those sources; without one it uses a deterministic offline heuristic.
- **Report** — per-citation status + a summary and overall risk level.

Statuses use deliberately careful wording — never "fake" or "good law":

| Status | Meaning |
|---|---|
| ✅ Verified in dataset | A trusted source clearly matches the same authority |
| ❌ Not found in dataset | No match — possible hallucination or outside the sandbox |
| ⚠️ Uncertain match | Similar authority found (typo / citation mismatch) |
| 🔎 Requires manual review | Partly supported; needs a human to confirm |

## Runs locally — no cloud required

Everything runs on your machine: local ChromaDB, local embeddings, local Streamlit. The **only** optional cloud touchpoint is the Claude API for higher-quality verification — and that's strictly optional. With no API key, QueLaw runs and demos **fully offline** using the heuristic verifier.

## Quick start

Target **Python 3.12** (newer versions may lack ChromaDB wheels).

```bash
# 1. Create and activate a virtual environment
py -3.12 -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/cmd)
# source .venv/bin/activate       # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) enable Claude — otherwise it runs offline
copy .env.example .env            # then add ANTHROPIC_API_KEY

# 4. Build the vector index from the sandbox (first run downloads the embedder)
python scripts/ingest.py

# 5a. Run the app
streamlit run app.py

# 5b. …or run the golden-path smoke test in the terminal
python scripts/check_demo.py
```

In the app: click **Load demo draft**, then **Check Draft**. The demo memo cites
a real case (`Spandeck … [2007] SGCA 37` → verified), a fabricated one
(`Tan Ah Kow v Singapore Airlines [2025] SGHC 999` → not found), plus a statute
and a rule.

## Project layout

```
app.py                  # Streamlit UI
scripts/ingest.py       # build the ChromaDB vector store from the sandbox
scripts/check_demo.py   # end-to-end golden-path smoke test
quelaw/
  extraction.py         # regex (+ optional LLM) citation extraction
  vectorstore.py        # ChromaDB ingest + retrieval
  verification.py       # heuristic + LLM verification logic
  llm.py                # optional Claude layer (grounded, JSON output)
  report.py             # summary stats + risk level
  schema.py             # data types + controlled status vocabulary
data/sandbox/           # Micro-LawNet proof-of-concept dataset (cases/statutes/rules)
data/demo/              # golden-path demo input
tests/                  # extraction unit tests
```

## The sandbox dataset

`data/sandbox/` holds a deliberately small, controlled set of Singapore
authorities as JSON. Entries are **paraphrased or placeholder** summaries with
**placeholder URLs** — a proof-of-concept, *not* authoritative legal text. Live
LawNet integration is treated as a future/bonus pathway, not a dependency.

## Tests

```bash
python -m pytest          # if pytest is installed
python tests/test_extraction.py   # plain-assert fallback runner
```

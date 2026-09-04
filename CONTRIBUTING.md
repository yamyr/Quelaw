# Contributing to Quelaw

Quelaw is a Python 3.14 Streamlit application. Keep contributions focused on reliable citation checking against the documented sandbox, and preserve the distinction between a dataset match and a legal conclusion. Use **Quelaw** for the product name and `quelaw` for the Python package and identifiers.

## Development environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```bash
uv sync --locked
uv run --locked streamlit run app.py
```

The project uses `.python-version` for Python selection, `pyproject.toml` for dependency declarations and the required uv version, and `uv.lock` for the resolved environment. Use a uv version within `tool.uv.required-version` (currently `>=0.12.7,<0.13`); CI and the canonical requirements export use uv `0.12.9`. The supported range also accommodates Dependabot's bundled uv updater. The development dependency group is included by default. Initial installation requires network access; demo verification requires no API key, vector index, or model download after setup.

Use `.env.example` for optional Claude configuration. Keep `.env`, Streamlit secrets, `.venv/`, and the generated `chroma/` index out of version control. Use the supplied demo text in issue reports and UI screenshots instead of private legal drafts.

## Verification before a pull request

```bash
uv sync --locked
uv pip check
uv run --locked python scripts/check_dataset.py
uv run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json
uv run --locked python -m pytest
uv run --locked python -m compileall -q app.py quelaw scripts
uv run --locked ruff check --select F821 app.py quelaw scripts tests
uv run --locked python scripts/check_demo_scenarios.py
uv run --locked python scripts/check_demo.py
```

Leave `ANTHROPIC_API_KEY` unset for the golden-path smoke run. The scenario checker forces `use_llm=False` independently of configuration. The evaluation command forbids network and API access and requires no vector index or embedding model after the locked dependencies are installed. CI validates the dataset, evaluates the committed baseline, runs full tests and demo checks, checks undefined names using the locked Ruff development dependency, and verifies requirements export drift.

For behavior changes, add a focused regression case at the affected boundary. Keep scenario expectations synchronized with `quelaw/demo.py` and `data/demo/test_memo_expected.md`. For UI changes, check the app in a browser as well as AppTest: native UI rendering and HTML annotations need visual inspection. Follow the existing [design conventions](docs/DESIGN.md).

## Dependency changes

Edit dependencies through uv so declarations and the lockfile remain synchronized. Add a runtime dependency with `uv add PACKAGE` or a development tool with `uv add --dev PACKAGE`. For an intentional upgrade, use `uv lock --upgrade-package PACKAGE`, then sync and run the checks above.

Regenerate the pip-compatible runtime export after any dependency change:

```bash
uv export --locked --no-dev --no-hashes --no-emit-project --output-file requirements.txt
```

Commit `pyproject.toml`, `uv.lock`, and the generated `requirements.txt` together when they change. Do not hand-edit the export or duplicate its version pins in documentation. Dependabot updates the uv manifest and lockfile weekly; regenerate the requirements export on each dependency PR before merging. CI rejects an export that differs from the lockfile. `requirements.txt` excludes development tools and supports consumers that install through pip. Community Cloud selects `uv.lock` when both files are present, according to its [dependency selection rules](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

`uv lock --check` verifies that declarations and the lockfile agree. The `--locked` flag makes normal sync and run commands fail on an outdated lockfile instead of silently changing it; see the [uv documentation](https://docs.astral.sh/uv/concepts/projects/sync/).

## Dataset and result changes

Every source record must have a unique `document_id` and validated provenance: text kind, coverage, official URL when known, retrieval date, version, reuse status/basis, and limitations. Keep unknown fields null and reuse unverified until evidence supports a stronger value. Placeholder URLs are not official URLs. `reuse_status="permitted"` requires an explicit basis. The existing nine records remain five paraphrases and four synthetic summaries; their legacy dates and URLs are not provenance evidence.

Run the dataset checker after any source change and record the new fingerprint with the change. Text and provenance affect that identity; JSON key order does not. Rebuild the optional retrieval index explicitly when the fingerprint changes. A changed dataset must not silently reuse an index or report for an earlier fingerprint.

Preserve every validated citation occurrence, even if several share the same authority identity. Corrections must carry the reviewed draft SHA-256, offsets, expected text, and replacement; reject stale or overlapping proposals before applying any. After a correction or other edit, invalidate the old report and recheck. A result of **Not found in dataset** must not become a claim that an authority does not exist. Quotation evidence must reflect the available source's fidelity and coverage, and cannot authenticate the current summary-only sandbox.

Report exports use schema `2`. Changes must preserve material parity between the app, JSON, and Markdown: draft/dataset identities, verifier/fallback details, occurrence and distinct-authority counts, finding/source IDs, review reasons, quotation states, and correction proposals. A contract change requires an explicit schema decision and export regressions.

## Evaluation changes

Keep inputs, expected occurrence spans and parsed fields, authority/quotation states, failure category, and reviewer status together in `data/evaluation/v1/cases.jsonl`. The corpus has at least 30 engineering fixtures, including clearly labeled synthetic cases. See its [README](data/evaluation/v1/README.md) for the case contract and baseline maintenance procedure.

Specify expectations independently of the runner's actual output. Review every material difference before updating `baseline.json`; never approve drift because an aggregate score improved. Keep extraction precision/recall and span accuracy separate from verification confusion counts and quotation outcomes. Changes in coverage can legitimately alter expected outcomes, but the review must say whether source coverage or matching behavior caused each difference.

Keep `reviewer_status="legal_domain_review_pending"` until a qualified domain review is recorded. Engineering checks and mocked Claude boundary tests do not validate legal holdings, coverage, quotation authenticity, or live model behavior. Record live API or real retrieval checks separately when performed.

## Release demonstration

Version 0.2.0 remains an untagged candidate. Complete the checks above from a fresh locked environment, confirm the runtime requirements export has no drift, and record the tested commit, Python/uv versions, dataset fingerprint, evaluation summary, and any untested paths. Recheck the [four unresolved ChromaDB advisories](CHANGELOG.md#unresolved-chromadb-advisories) against the installed version and keep unresolved findings visible.

Run the app without `ANTHROPIC_API_KEY`, leave demo mode off, and save this synthetic review memo as a temporary `.txt` file:

```text
ACB v Thomson Medical Pte Ltd [2016] SGCA 20 is cited in the first paragraph.
ACB v Thomson Medical Pte Ltd [2016] SGCA 20 is cited in the second paragraph.
ACB v Thomson Medical Pte Ltd [2016] SGCA 20 is cited in the third paragraph.
```

1. Upload the memo and check the draft. Confirm three selectable occurrences and one distinct cited authority before correction.
2. Select the second occurrence using the keyboard and inspect its context, matched source ID, summary/paraphrase provenance, unknown source details, and review reason.
3. Inspect the correction preview to the dataset citation `[2017] SGCA 20`. Apply only that occurrence's proposal. Confirm the first and third occurrences are unchanged and the previous report is invalidated.
4. Recheck the edited draft. Inspect the new finding and confirm the report is bound to the edited draft hash and current dataset fingerprint.
5. Download both Markdown and JSON from that report. Compare schema version, draft/dataset identities, finding IDs, statuses, source IDs, quotation states, review reasons, and any remaining correction proposals with the app.
6. Repeat finding selection, evidence reading, correction/recheck, and export at a 390 px viewport. Record browser/keyboard evidence and any layout or interaction failures.

Independent review, green CI, and recorded release demonstration evidence are required before a `v0.2.0` tag. Legal domain review remains separately pending unless documented. Tagging and deployment require an explicit release instruction; the candidate documentation does not authorize or perform either action.

Describe a pull request by its changed behavior, the reason for the change, and the checks run. Mention any untested API or retrieval path explicitly. Keep broader source integration and evaluation proposals tied to the [roadmap](ROADMAP.md).

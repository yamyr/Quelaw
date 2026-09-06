# Contributing to Quelaw

Quelaw is a Python 3.14 Streamlit application. Keep contributions focused on reliable citation checking against the documented sandbox, and preserve the distinction between a dataset match and a legal conclusion. Use **Quelaw** for the product name and `quelaw` for the Python package and identifiers.

## Development environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```bash
make setup
make dev-offline
```

These shortcuts require GNU Make (included on typical macOS/Linux development setups). Run `make help` for the command list. On Windows without Make, use the underlying `uv` commands shown in the Makefile or run them through WSL. The portable app command remains `uv run --locked streamlit run app.py`.

The project uses `.python-version` for Python selection, `pyproject.toml` for dependency declarations and the required uv version, and `uv.lock` for the resolved environment. Use a uv version within `tool.uv.required-version` (currently `>=0.12.7,<0.13`); CI and the canonical requirements export use uv `0.12.9`. The supported range also accommodates Dependabot's bundled uv updater. The development dependency group is included by default. Initial installation requires network access; demo verification requires no API key, vector index, or model download after setup.

Use `.env.example` for optional Claude configuration. Keep `.env`, Streamlit secrets, `.venv/`, and the generated `chroma/` index out of version control. Use the supplied demo text in issue reports and UI screenshots instead of private legal drafts.

## Daily development

| Command | Purpose |
|---|---|
| `make dev-offline` | Start the app with Claude disabled, even when `.env` contains a key. |
| `make dev` | Start the app with the normal optional Claude configuration. |
| `make check-fast` | Run correctness lint, source validation, and the offline evaluation baseline. |
| `make test TEST_ARGS="tests/test_extraction.py -x"` | Run one test file and stop on its first failure. |
| `make test TEST_ARGS="--lf"` | Rerun the last failing tests. |
| `make check` | Run the complete verification gate used in CI. |

Pass Streamlit flags with `APP_ARGS`, for example `make dev-offline APP_ARGS="--server.port 8502"`. Stop the server with Ctrl-C. These commands use the committed environment without silently updating the lockfile.

The public pipeline and verification functions load current source evidence at the beginning of each call. Editing a sandbox JSON file no longer requires a Python restart or manual cache reset. One pipeline call shares a single immutable dataset across all occurrences. For a batch that deliberately uses a fixed snapshot, call `load_dataset(...)` once and pass `dataset=...`; load it again when you want source edits to take effect. Invalid source edits raise `DatasetValidationError` on the next check. The optional index still requires an explicit rebuild after source changes.

## Verification before a pull request

```bash
make setup
make check
```

`make check` checks the lockfile and installed packages, compares the runtime export without rewriting it, compiles modules, runs correctness lint, validates sources, evaluates all 48 baseline cases, runs the entire test suite, and exercises both demo commands. It always runs all tests, even if `TEST_ARGS` is set for everyday development. CI runs these same targets and cancels obsolete runs for the same branch.

Both demo commands force offline verification independently of Claude configuration. The test and evaluation targets also clear the API key for their process. The evaluation command forbids network and API access and requires no vector index or embedding model after installation. The Ruff rules live in `pyproject.toml` and cover syntax errors, invalid comparisons/control flow, and undefined names; this is a correctness gate, not a repository-wide formatting migration.

For behavior changes, add a focused regression case at the affected boundary. Keep scenario expectations synchronized with `quelaw/demo.py` and `data/demo/test_memo_expected.md`. For UI changes, check the app in a browser as well as AppTest: native UI rendering and HTML annotations need visual inspection. Follow the existing [design conventions](docs/DESIGN.md).

## Dependency changes

Edit dependencies through uv so declarations and the lockfile remain synchronized. Add a runtime dependency with `uv add PACKAGE` or a development tool with `uv add --dev PACKAGE`. For an intentional upgrade of all compatible dependencies:

```bash
make upgrade
make check
```

Review the manifest, lock and export diff before committing. `make upgrade` resolves within declared constraints, synchronizes the environment, then regenerates the runtime export; it does not approve changed behavior or security findings. For a single package, use `uv lock --upgrade-package PACKAGE`, `make setup`, `make export`, then `make check`. Parent constraints can hold transitive packages below their newest published release; do not override those pins just to empty an outdated-package list. See uv's [upgrade rules](https://docs.astral.sh/uv/concepts/projects/sync/#upgrading-locked-package-versions).

Regenerate the pip-compatible runtime export after any dependency change:

```bash
make export
```

Commit `pyproject.toml`, `uv.lock`, and the generated `requirements.txt` together when they change. Do not hand-edit the export or duplicate its version pins in documentation. Dependabot updates the uv manifest and lockfile weekly; regenerate the requirements export on each dependency PR before merging. `make export-check` and CI reject dependency or annotation drift without changing the working file; only uv's two generated command-header lines are ignored. `requirements.txt` excludes development tools and supports consumers that install through pip. Community Cloud selects `uv.lock` when both files are present, according to its [dependency selection rules](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

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

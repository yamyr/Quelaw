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
uv run --locked python -m pytest
uv run --locked python -m compileall -q app.py quelaw scripts
uv run --locked python scripts/check_demo_scenarios.py
uv run --locked python scripts/check_demo.py
```

Leave `ANTHROPIC_API_KEY` unset for the golden-path smoke run. The scenario checker forces `use_llm=False` independently of configuration. Tests cover extraction, verification, annotations, curated scenarios, and Streamlit interactions; CI installs the actual runtime dependencies and runs the offline checks without Claude credentials.

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

Document the source and scope of every sandbox addition. Keep placeholder or paraphrased material clearly identified, and update expected outcomes when coverage changes. A result of **Not found in dataset** must not become a claim that an authority does not exist. Quote hints and proposed corrections must retain human review and re-verification steps.

Describe a pull request by its changed behavior, the reason for the change, and the checks run. Mention any untested API or retrieval path explicitly. Keep broader source integration and evaluation proposals tied to the [roadmap](ROADMAP.md).

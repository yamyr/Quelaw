.DEFAULT_GOAL := help
UV ?= uv
TEST_ARGS ?=
APP_ARGS ?=

.PHONY: help setup dev dev-offline check check-fast lint test dataset evaluate demo export export-check upgrade

help:
	@printf '%s\n' \
	  'make setup        Install the locked development environment' \
	  'make dev          Start Streamlit with local Claude configuration' \
	  'make dev-offline  Start Streamlit with Claude disabled' \
	  'make check-fast   Run lint, source validation and offline evaluation' \
	  'make test         Run tests; TEST_ARGS="tests/test_extraction.py -x" narrows the run' \
	  'make check        Run the complete local/CI verification gate' \
	  'make demo         Run all offline scenarios and the smoke memo' \
	  'make export       Regenerate runtime requirements from the lock' \
	  'make export-check Check export drift without modifying files' \
	  'make upgrade      Upgrade compatible packages, sync and regenerate the export'

setup:
	$(UV) sync --locked

dev:
	$(UV) run --locked streamlit run app.py $(APP_ARGS)

dev-offline:
	ANTHROPIC_API_KEY= STREAMLIT_BROWSER_GATHER_USAGE_STATS=false $(UV) run --locked streamlit run app.py $(APP_ARGS)

check:
	$(UV) lock --check
	$(UV) pip check
	$(MAKE) export-check
	$(UV) run --locked python -m compileall -q app.py quelaw scripts
	$(MAKE) check-fast
	$(MAKE) test TEST_ARGS=
	$(MAKE) demo

check-fast: lint dataset evaluate

lint:
	$(UV) run --locked ruff check app.py quelaw scripts tests

test:
	ANTHROPIC_API_KEY= STREAMLIT_BROWSER_GATHER_USAGE_STATS=false $(UV) run --locked pytest -q $(TEST_ARGS)

dataset:
	$(UV) run --locked python scripts/check_dataset.py

evaluate:
	ANTHROPIC_API_KEY= $(UV) run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json

demo:
	$(UV) run --locked python scripts/check_demo_scenarios.py
	$(UV) run --locked python scripts/check_demo.py

export:
	$(UV) export --locked --no-dev --no-hashes --no-emit-project --output-file requirements.txt

export-check:
	@set -eu; tmp=$$(mktemp -d); \
	trap 'rm -f "$$tmp/expected" "$$tmp/actual"; rmdir "$$tmp"' 0; \
	sed '1,2d' requirements.txt > "$$tmp/expected"; \
	$(UV) export --locked --no-dev --no-hashes --no-emit-project --no-header > "$$tmp/actual"; \
	diff -u "$$tmp/expected" "$$tmp/actual"

upgrade:
	$(UV) lock --upgrade
	$(UV) sync --locked
	$(MAKE) export

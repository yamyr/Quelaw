#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = ["pydantic>=2.10,<3"]
# ///
# ─── How to run ───
# 1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run with the locked project: uv run --locked python scripts/check_dataset.py
# 3. Or run standalone: uv run scripts/check_dataset.py --dataset data/sandbox
# ──────────────────
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quelaw.config import SANDBOX_DIR  # noqa: E402
from quelaw.provenance import DatasetValidationError, load_dataset  # noqa: E402


class DatasetArguments(argparse.Namespace):
    dataset: Path = SANDBOX_DIR


def main() -> int:
    """Validate a local source inventory and print its identity and coverage."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--dataset", type=Path, default=SANDBOX_DIR)
    arguments = DatasetArguments()
    parser.parse_args(namespace=arguments)
    try:
        inventory = load_dataset(arguments.dataset)
    except DatasetValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({
        "fingerprint": inventory.fingerprint,
        "records": len(inventory.records),
        "text_kind": dict(sorted(Counter(record.provenance.text_kind for record in inventory.records).items())),
        "coverage": dict(sorted(Counter(record.provenance.coverage for record in inventory.records).items())),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

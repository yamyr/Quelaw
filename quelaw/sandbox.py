"""Loader for the Micro-LawNet sandbox.

The sandbox is a small, controlled, clearly-labelled proof-of-concept dataset of
Singapore legal materials stored as JSON files under ``data/sandbox/``.
"""
from __future__ import annotations

from typing import List

from .config import SANDBOX_DIR
from .provenance import Dataset, load_dataset


def load_documents() -> List[dict]:
    """Load every sandbox document (cases, statutes, rules)."""
    docs: List[dict] = []
    dataset = load_dataset(SANDBOX_DIR)
    for path, record in zip(sorted(SANDBOX_DIR.rglob("*.json")), dataset.records, strict=True):
        doc = record.model_dump(mode="json", exclude_unset=True)
        doc["_path"] = str(path)
        docs.append(doc)
    return docs


def load_current_dataset() -> Dataset:
    """Read fresh evidence once per check; callers can pass a snapshot explicitly."""
    return load_dataset(SANDBOX_DIR)

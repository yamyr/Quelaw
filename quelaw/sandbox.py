"""Loader for the Micro-LawNet sandbox.

The sandbox is a small, controlled, clearly-labelled proof-of-concept dataset of
Singapore legal materials stored as JSON files under ``data/sandbox/``.
"""
from __future__ import annotations

from functools import lru_cache
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


@lru_cache(maxsize=1)
def dataset_cached() -> Dataset:
    """Cached immutable source evidence for repeated checks in one session."""
    return load_dataset(SANDBOX_DIR)


@lru_cache(maxsize=1)
def _cached_documents() -> tuple:
    return tuple(load_documents())


def documents_cached() -> List[dict]:
    """Cached view of the sandbox (cheap repeated reads during a request)."""
    return list(_cached_documents())


def reset_cache() -> None:
    _cached_documents.cache_clear()
    dataset_cached.cache_clear()

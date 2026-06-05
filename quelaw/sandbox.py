"""Loader for the Micro-LawNet sandbox.

The sandbox is a small, controlled, clearly-labelled proof-of-concept dataset of
Singapore legal materials stored as JSON files under ``data/sandbox/``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import List

from .config import SANDBOX_DIR


def load_documents() -> List[dict]:
    """Load every sandbox document (cases, statutes, rules)."""
    docs: List[dict] = []
    if not SANDBOX_DIR.exists():
        return docs
    for path in sorted(SANDBOX_DIR.rglob("*.json")):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        doc["_path"] = str(path)
        docs.append(doc)
    return docs


@lru_cache(maxsize=1)
def _cached_documents() -> tuple:
    return tuple(load_documents())


def documents_cached() -> List[dict]:
    """Cached view of the sandbox (cheap repeated reads during a request)."""
    return list(_cached_documents())


def reset_cache() -> None:
    _cached_documents.cache_clear()

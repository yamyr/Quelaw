"""Configuration and environment for QueLaw.

Everything runs locally. The only optional cloud touchpoint is the Claude API,
which is enabled purely by the presence of ANTHROPIC_API_KEY. With no key, the
app falls back to a fully offline heuristic verifier.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv not installed yet — env vars still work
    pass

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent

DATA_DIR = ROOT_DIR / "data"
SANDBOX_DIR = DATA_DIR / "sandbox"
DEMO_DIR = DATA_DIR / "demo"
CHROMA_DIR = ROOT_DIR / "chroma"

COLLECTION_NAME = "micro_lawnet"
TOP_K = 4

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
# Sensible default: fast + capable enough for a citation-comparison task.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def llm_enabled() -> bool:
    """True when a Claude API key is present (upgrades verification quality)."""
    return bool(ANTHROPIC_API_KEY)

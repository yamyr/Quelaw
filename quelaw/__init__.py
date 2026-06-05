"""QueLaw — Singapore legal citation hallucination checker (hackathon MVP).

The package is import-light: heavy/optional dependencies (chromadb, anthropic)
are imported lazily inside the functions that need them, so you can import and
unit-test the extraction logic without a vector DB or an API key.
"""

__version__ = "0.1.0"

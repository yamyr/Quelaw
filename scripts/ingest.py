"""Build (or rebuild) the Micro-LawNet vector store from the sandbox.

    py -3.12 scripts/ingest.py

On first run this downloads the small local embedding model (~once), then runs
fully offline.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw.vectorstore import ingest  # noqa: E402


def main() -> None:
    print("Ingesting sandbox into the local vector store…")
    n = ingest(reset=True)
    print(f"Done. Indexed {n} chunk(s) into ChromaDB.")
    if n == 0:
        print("WARNING: no documents found under data/sandbox/.")


if __name__ == "__main__":
    main()

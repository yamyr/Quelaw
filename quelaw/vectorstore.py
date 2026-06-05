"""ChromaDB-backed retrieval for the RAG pipeline.

Uses a local, on-disk ChromaDB with its built-in embedding function (a small
MiniLM ONNX model). The model is downloaded once on first ingest, then runs
fully offline — no hosted vector DB, no embeddings API.
"""
from __future__ import annotations

from typing import List

from .config import CHROMA_DIR, COLLECTION_NAME, TOP_K
from .sandbox import load_documents

# Metadata keys we persist alongside each chunk (None values are coerced to "").
_META_KEYS = (
    "document_id",
    "title",
    "citation",
    "source_type",
    "court",
    "section",
    "provision",
    "source_url",
    "status",
)


def _client():
    import chromadb  # lazy: keeps the package importable without chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection():
    return _client().get_or_create_collection(name=COLLECTION_NAME)


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def _meta_for(doc: dict, chunk_index: int) -> dict:
    meta = {k: (doc.get(k) if doc.get(k) is not None else "") for k in _META_KEYS}
    meta["chunk"] = chunk_index
    return meta


def _embeddable(doc: dict, chunk: str) -> str:
    # Prepend the title + citation so retrieval matches on the authority itself,
    # not just on the body text.
    header = " ".join(
        str(doc.get(k, "")) for k in ("title", "citation", "provision", "section")
    ).strip()
    return f"{header}\n{chunk}".strip()


def ingest(reset: bool = True) -> int:
    """(Re)build the vector store from the sandbox. Returns the chunk count."""
    client = _client()
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    col = client.get_or_create_collection(name=COLLECTION_NAME)

    ids, documents, metadatas = [], [], []
    for doc in load_documents():
        doc_id = doc.get("document_id") or doc.get("title", "doc")
        chunks = chunk_text(doc.get("text", "")) or [doc.get("title", "")]
        for i, ch in enumerate(chunks):
            ids.append(f"{doc_id}_chunk_{i}")
            documents.append(_embeddable(doc, ch))
            meta = _meta_for(doc, i)
            meta["chunk_text"] = ch
            metadatas.append(meta)

    if ids:
        col.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def count() -> int:
    try:
        return get_collection().count()
    except Exception:
        return 0


def query(text: str, n_results: int = TOP_K) -> List[dict]:
    """Return the top matching chunks for ``text`` (empty list if not built)."""
    try:
        col = get_collection()
        total = col.count()
    except Exception:
        return []
    if total == 0:
        return []

    res = col.query(query_texts=[text], n_results=min(n_results, total))
    out: List[dict] = []
    ids = res.get("ids", [[]])[0]
    for i in range(len(ids)):
        meta = res["metadatas"][0][i] or {}
        out.append(
            {
                "id": ids[i],
                "distance": res["distances"][0][i],
                "document": res["documents"][0][i],
                "metadata": meta,
                "excerpt": meta.get("chunk_text") or res["documents"][0][i],
            }
        )
    return out

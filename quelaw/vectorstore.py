"""Local retrieval bound to a validated dataset's source identities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .config import CHROMA_DIR, COLLECTION_NAME, SANDBOX_DIR, TOP_K
from .provenance import Dataset, SourceRecord, load_dataset

if TYPE_CHECKING:
    from chromadb import Collection
    from chromadb.api import ClientAPI
    from chromadb.api.types import Embeddings, Metadata

type Embedder = Callable[[list[str]], Embeddings]
INDEX_VERSION: Final = 1


class IndexRebuildRequired(RuntimeError):
    """A persisted index cannot establish its relationship to current evidence."""

    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Index rebuild required: {reason}. Rebuild the index with ingest(reset=True).")


class _IndexMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, frozen=True, extra="forbid")

    dataset_fingerprint: str
    index_version: int


class _ChunkMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, frozen=True, extra="forbid")

    dataset_fingerprint: str
    document_id: str
    chunk_index: int

    def persisted(self) -> Metadata:
        return {
            "dataset_fingerprint": self.dataset_fingerprint,
            "document_id": self.document_id, "chunk_index": self.chunk_index,
        }


@dataclass(frozen=True, slots=True)
class _Chunk:
    id: str
    document: str
    metadata: _ChunkMetadata
    record: SourceRecord


def _client(persist_dir: Path | None = None) -> ClientAPI:
    import chromadb
    from chromadb.errors import InternalError

    try:
        return chromadb.PersistentClient(path=str(persist_dir if persist_dir is not None else CHROMA_DIR))
    except InternalError as error:
        raise IndexRebuildRequired(f"local index storage cannot be opened: {error}") from error
    except AttributeError as error:
        if str(error) != "'RustBindingsAPI' object has no attribute 'bindings'":
            raise
        raise IndexRebuildRequired("Chroma retained an incomplete storage initialization") from error


def get_collection(persist_dir: Path | None = None) -> Collection | None:
    """Open an existing collection without creating an empty index."""
    from chromadb.errors import NotFoundError

    path = persist_dir if persist_dir is not None else CHROMA_DIR
    if not path.exists():
        return None
    try:
        return _client(path).get_collection(name=COLLECTION_NAME, embedding_function=None)
    except NotFoundError:
        return None


def collection_exists(persist_dir: Path | None = None) -> bool:
    return get_collection(persist_dir) is not None


def index_status(
    dataset: Dataset, *, persist_dir: Path | None = None,
) -> Literal["missing", "ready", "stale"]:
    """Inspect index integrity without embedding, downloads, or index mutation."""
    try:
        collection = get_collection(persist_dir)
        if collection is None:
            return "missing"
        _ = _validated_chunks(collection, dataset)
    except IndexRebuildRequired:
        return "stale"
    return "ready"


def count(persist_dir: Path | None = None) -> int:
    try:
        collection = get_collection(persist_dir)
        return collection.count() if collection is not None else 0
    except IndexRebuildRequired:
        return 0


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    return [
        chunk for start in range(0, len(text), size - overlap)
        if (chunk := text[start:start + size].strip())
    ]


def _chunks(dataset: Dataset) -> list[_Chunk]:
    chunks: list[_Chunk] = []
    for record in dataset.records:
        header = " ".join(value for value in (
            record.title, record.citation, record.provision, record.section,
        ) if value is not None)
        for index, text in enumerate(chunk_text(record.text)):
            chunks.append(_Chunk(
                id=f"{dataset.fingerprint}:{record.document_id}:{index}",
                document=f"{header}\n{text}",
                metadata=_ChunkMetadata(
                    dataset_fingerprint=dataset.fingerprint,
                    document_id=record.document_id, chunk_index=index,
                ),
                record=record,
            ))
    return chunks


def _validated_chunks(collection: Collection, dataset: Dataset) -> list[_Chunk]:
    try:
        metadata = _IndexMetadata.model_validate(collection.metadata)
    except ValidationError as error:
        raise IndexRebuildRequired("collection identity metadata is missing or invalid") from error
    if metadata.dataset_fingerprint != dataset.fingerprint or metadata.index_version != INDEX_VERSION:
        raise IndexRebuildRequired("dataset fingerprint or index version has changed")
    chunks = _chunks(dataset)
    expected = {chunk.id: chunk for chunk in chunks}
    stored = collection.get(include=["metadatas", "documents"])
    documents, metadatas = stored["documents"], stored["metadatas"]
    if (
        documents is None or metadatas is None
        or len(documents) != len(chunks) or len(metadatas) != len(chunks)
        or len(stored["ids"]) != len(chunks) or set(stored["ids"]) != set(expected)
    ):
        raise IndexRebuildRequired("stored chunk inventory does not match the dataset")
    for chunk_id, document, raw_metadata in zip(stored["ids"], documents, metadatas, strict=True):
        chunk = expected[chunk_id]
        try:
            chunk_metadata = _ChunkMetadata.model_validate(raw_metadata)
        except ValidationError as error:
            raise IndexRebuildRequired(f"chunk {chunk_id!r} has invalid identity metadata") from error
        if chunk_metadata != chunk.metadata or document != chunk.document:
            raise IndexRebuildRequired(f"chunk {chunk_id!r} does not match its source")
    return chunks


def _embeddings(texts: list[str], embedding_function: Embedder | None) -> Embeddings:
    if embedding_function is not None:
        return embedding_function(texts)
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()(texts)


def ingest(
    reset: bool = True, *, dataset: Dataset | None = None,
    persist_dir: Path | None = None, embedding_function: Embedder | None = None,
) -> int:
    """Build local chunks; explicit embeddings allow offline test or custom encoders."""
    evidence = dataset if dataset is not None else load_dataset(SANDBOX_DIR)
    chunks = _chunks(evidence)
    client = _client(persist_dir)
    existing = get_collection(persist_dir)
    if not reset and existing is not None:
        return len(_validated_chunks(existing, evidence))
    if reset and existing is not None:
        client.delete_collection(COLLECTION_NAME)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=None,
        metadata={"dataset_fingerprint": evidence.fingerprint, "index_version": INDEX_VERSION},
    )
    if chunks:
        documents = [chunk.document for chunk in chunks]
        collection.upsert(
            ids=[chunk.id for chunk in chunks], documents=documents,
            metadatas=[chunk.metadata.persisted() for chunk in chunks],
            embeddings=_embeddings(documents, embedding_function),
        )
    return len(chunks)


def query(
    text: str, n_results: int = TOP_K, *, dataset: Dataset | None = None,
    persist_dir: Path | None = None, embedding_function: Embedder | None = None,
) -> list[SourceRecord]:
    """Return current source objects in retrieval order, without duplicate sources."""
    if not text.strip() or n_results <= 0:
        return []
    collection = get_collection(persist_dir)
    if collection is None:
        return []
    evidence = dataset if dataset is not None else load_dataset(SANDBOX_DIR)
    chunks = {chunk.id: chunk for chunk in _validated_chunks(collection, evidence)}
    if not chunks:
        return []
    result = collection.query(
        query_embeddings=_embeddings([text], embedding_function),
        n_results=min(n_results, collection.count()), include=[],
    )
    sources: dict[str, SourceRecord] = {}
    for chunk_id in result["ids"][0]:
        if chunk_id not in chunks:
            raise IndexRebuildRequired("query returned an unknown source identity")
        source = chunks[chunk_id].record
        _ = sources.setdefault(source.document_id, source)
    return list(sources.values())

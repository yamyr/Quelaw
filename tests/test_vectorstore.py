from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Never

import chromadb
import numpy as np
import pytest
from chromadb.api.types import Embeddings

from quelaw import vectorstore
from quelaw.config import COLLECTION_NAME
from quelaw.provenance import Dataset, load_dataset


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_connection(
        _connection: socket.socket, address: str | tuple[str, int] | tuple[str, int, int, int],
    ) -> Never:
        pytest.fail(f"Local retrieval attempted network connection: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)


def make_dataset(root: Path, text: str = "apple authority") -> Dataset:
    root.mkdir(parents=True, exist_ok=True)
    for document_id, source_text in (("apple", text), ("pear", "pear authority")):
        payload = {
            "document_id": document_id, "title": document_id,
            "source_type": "case", "source_url": "legacy placeholder",
            "status": "sample", "text": source_text,
            "provenance": {
                "text_kind": "synthetic", "coverage": "summary", "official_url": None,
                "retrieved_on": None, "version_label": None, "reuse_status": "unverified",
                "reuse_basis": None, "limitations": ["Fixture only."],
            },
        }
        _ = (root / f"{document_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return load_dataset(root)


def local_embeddings(texts: list[str]) -> Embeddings:
    return [
        np.array([float("apple" in text), float("pear" in text)], dtype=np.float32)
        for text in texts
    ]


def unexpected_embeddings(_texts: list[str]) -> Never:
    pytest.fail("A stale or missing index must not embed query text")


def test_query_returns_supplied_source_when_real_persistent_index_is_built(tmp_path: Path) -> None:
    # Given a non-default dataset and a real local Chroma index.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    added = vectorstore.ingest(
        dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings,
    )
    # When searching through a separately opened persistent collection.
    results = vectorstore.query(
        "apple", 1, dataset=dataset, persist_dir=persist_dir,
        embedding_function=local_embeddings,
    )
    # Then the hit is the original supplied record, with its unknown provenance intact.
    assert added == 2
    assert len(results) == 1
    assert results[0] is dataset.records[0]
    assert results[0].provenance.official_url is None
    persisted = chromadb.PersistentClient(path=str(persist_dir)).get_collection(COLLECTION_NAME)
    assert persisted.metadata is not None
    assert persisted.metadata["dataset_fingerprint"] == dataset.fingerprint


def test_query_refuses_changed_dataset_before_embedding(tmp_path: Path) -> None:
    # Given an index built from earlier source text.
    original = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=original, persist_dir=persist_dir, embedding_function=local_embeddings)
    changed = make_dataset(tmp_path / "sources", "apple changed authority")
    # When querying with changed evidence, then stale chunks require explicit rebuilding.
    with pytest.raises(vectorstore.IndexRebuildRequired, match="[Rr]ebuild"):
        _ = vectorstore.query("apple", dataset=changed, persist_dir=persist_dir, embedding_function=unexpected_embeddings)


@pytest.mark.parametrize("empty", [False, True])
def test_query_refuses_legacy_collection_without_fingerprint(tmp_path: Path, empty: bool) -> None:
    # Given an existing collection without dataset identity metadata.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    collection = chromadb.PersistentClient(path=str(persist_dir)).create_collection(
        COLLECTION_NAME, embedding_function=None,
    )
    if not empty:
        collection.add(ids=["legacy"], embeddings=[[1.0, 0.0]], documents=["apple"])
    # When querying, then missing metadata is stale even on an empty legacy collection.
    with pytest.raises(vectorstore.IndexRebuildRequired):
        _ = vectorstore.query("apple", dataset=dataset, persist_dir=persist_dir, embedding_function=unexpected_embeddings)


@pytest.mark.parametrize("field,value", [
    ("document_id", "unrelated"), ("dataset_fingerprint", "stale"),
    ("chunk_index", 999), ("chunk_index", None), ("chunk_index", True),
])
def test_query_refuses_corrupt_chunk_metadata(
    tmp_path: Path, field: str, value: str | int | bool | None,
) -> None:
    # Given a persisted chunk has corrupt or missing identity metadata.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    collection = chromadb.PersistentClient(path=str(persist_dir)).get_collection(COLLECTION_NAME)
    chunk_id = collection.get()["ids"][0]
    collection.update(ids=[chunk_id], metadatas=[{field: value}])
    # When querying, then metadata cannot redirect retrieval to a different source.
    with pytest.raises(vectorstore.IndexRebuildRequired):
        _ = vectorstore.query("apple", dataset=dataset, persist_dir=persist_dir, embedding_function=unexpected_embeddings)


def test_query_refuses_changed_persisted_text(tmp_path: Path) -> None:
    # Given indexed text no longer corresponds to the current source chunk.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    collection = chromadb.PersistentClient(path=str(persist_dir)).get_collection(
        COLLECTION_NAME, embedding_function=None,
    )
    collection.update(ids=[collection.get()["ids"][0]], documents=["tampered"], embeddings=[[1.0, 0.0]])
    # When querying, then the index is refused before its stale text can rank sources.
    with pytest.raises(vectorstore.IndexRebuildRequired):
        _ = vectorstore.query("apple", dataset=dataset, persist_dir=persist_dir, embedding_function=unexpected_embeddings)


def test_ingest_without_reset_refuses_stale_index(tmp_path: Path) -> None:
    # Given a persisted index belongs to a prior dataset.
    original = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=original, persist_dir=persist_dir, embedding_function=local_embeddings)
    changed = make_dataset(tmp_path / "sources", "new apple evidence")
    # When ingestion omits reset, then it cannot silently repair or append to stale data.
    with pytest.raises(vectorstore.IndexRebuildRequired):
        _ = vectorstore.ingest(False, dataset=changed, persist_dir=persist_dir, embedding_function=local_embeddings)


def test_explicit_reset_replaces_stale_index(tmp_path: Path) -> None:
    # Given a previously indexed dataset has changed.
    original = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=original, persist_dir=persist_dir, embedding_function=local_embeddings)
    changed = make_dataset(tmp_path / "sources", "new apple evidence")
    # When the user explicitly rebuilds, then current source identity can be retrieved.
    _ = vectorstore.ingest(True, dataset=changed, persist_dir=persist_dir, embedding_function=local_embeddings)
    result = vectorstore.query("apple", 1, dataset=changed, persist_dir=persist_dir, embedding_function=local_embeddings)
    assert result[0] is changed.records[0]
    assert vectorstore.index_status(changed, persist_dir=persist_dir) == "ready"


def test_missing_index_reads_do_not_create_collection(tmp_path: Path) -> None:
    # Given no persistent index exists.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "missing"
    # When the sidebar and retrieval inspect it, then the absent index remains absent.
    assert vectorstore.count(persist_dir) == 0
    assert not vectorstore.collection_exists(persist_dir)
    assert vectorstore.index_status(dataset, persist_dir=persist_dir) == "missing"
    assert vectorstore.query("apple", dataset=dataset, persist_dir=persist_dir) == []
    assert not persist_dir.exists()


def test_query_deduplicates_chunks_of_same_source(tmp_path: Path) -> None:
    # Given a long source occupies several retrieved chunks.
    dataset = make_dataset(tmp_path / "sources", "apple authority " * 180)
    persist_dir = tmp_path / "index"
    added = vectorstore.ingest(dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    # When querying all chunks, then each original source occurs only once.
    results = vectorstore.query("apple", added, dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    assert len(results) == 2
    assert results[0] is dataset.records[0]
    assert results[1] is dataset.records[1]


@pytest.mark.parametrize("unexpected_chunk", [False, True])
def test_index_status_is_stale_when_chunk_inventory_changes(tmp_path: Path, unexpected_chunk: bool) -> None:
    # Given a source chunk was lost or an unknown chunk was inserted.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    _ = vectorstore.ingest(dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    collection = chromadb.PersistentClient(path=str(persist_dir)).get_collection(COLLECTION_NAME)
    if unexpected_chunk:
        collection.add(ids=["foreign"], documents=["apple"], embeddings=[[1.0, 0.0]])
    else:
        _ = collection.delete(ids=[collection.get()["ids"][0]])
    # When the sidebar checks integrity, then the index is stale without embedding.
    assert vectorstore.index_status(dataset, persist_dir=persist_dir) == "stale"


def test_ingest_without_reset_reuses_matching_index(tmp_path: Path) -> None:
    # Given an intact matching index already exists.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    original_count = vectorstore.ingest(dataset=dataset, persist_dir=persist_dir, embedding_function=local_embeddings)
    # When reset is false, then the ready index is retained without embedding again.
    assert vectorstore.ingest(
        False, dataset=dataset, persist_dir=persist_dir, embedding_function=unexpected_embeddings,
    ) == original_count


def test_chunk_text_keeps_single_chunk_at_size_boundary() -> None:
    # Given source text exactly fits the chunk size.
    text = "a" * 900
    # When splitting, then a duplicate trailing chunk is unnecessary.
    assert vectorstore.chunk_text(text) == [text]


def test_sidebar_remains_available_when_database_is_corrupt(tmp_path: Path) -> None:
    # Given Chroma's SQLite file is unreadable.
    dataset = make_dataset(tmp_path / "sources")
    persist_dir = tmp_path / "index"
    persist_dir.mkdir()
    _ = (persist_dir / "chroma.sqlite3").write_bytes(b"not a sqlite database")
    # When the sidebar reruns, then failed Chroma startup cannot hide the recovery controls.
    for _ in range(2):
        assert vectorstore.index_status(dataset, persist_dir=persist_dir) == "stale"
        assert vectorstore.count(persist_dir) == 0
    with pytest.raises(vectorstore.IndexRebuildRequired):
        _ = vectorstore.query("apple", dataset=dataset, persist_dir=persist_dir, embedding_function=unexpected_embeddings)

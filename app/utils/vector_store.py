"""
ChromaDB vector store wrapper.

Provides upsert and nearest-neighbour query over persistent ChromaDB collections.
Collections used:
  - test-case-index:      embedded test case descriptions
  - defect-history-index: embedded defect description strings
"""
from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

_client_instance: chromadb.Client | None = None


def _client() -> chromadb.Client:
    global _client_instance
    if _client_instance is None:
        db_path = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
        _client_instance = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client_instance


def _get_or_create_collection(name: str) -> chromadb.Collection:
    return _client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert(
    collection: str,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict] | None = None,
) -> None:
    """
    Upsert documents with pre-computed embeddings into a ChromaDB collection.

    Args:
        collection: Collection name (e.g. 'test-case-index')
        ids:        Unique string IDs for each document
        documents:  Raw text of each document
        embeddings: Pre-computed embedding vectors (must match Ollama embed output)
        metadatas:  Optional list of metadata dicts per document
    """
    col = _get_or_create_collection(collection)
    col.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas or [{} for _ in ids],
    )
    logger.debug("Upserted %d items into collection '%s'.", len(ids), collection)


def query(
    collection: str,
    query_embedding: list[float],
    n_results: int = 10,
    where: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Query a ChromaDB collection for the nearest neighbours to a query embedding.

    Args:
        collection:      Collection name
        query_embedding: Query vector (from llm_client.embed())
        n_results:       Number of nearest neighbours to return
        where:           Optional ChromaDB metadata filter dict

    Returns:
        List of result dicts, each with keys:
          id, document, metadata, distance (lower = more similar for cosine)
    """
    col = _get_or_create_collection(collection)

    # Guard: don't request more results than exist in the collection
    count = col.count()
    if count == 0:
        logger.warning("Collection '%s' is empty. Run seed_chroma.py first.", collection)
        return []
    n_results = min(n_results, count)

    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results":        n_results,
        "include":          ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "id":       doc_id,
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return output


def collection_count(collection: str) -> int:
    """Return the number of items currently in a collection."""
    return _get_or_create_collection(collection).count()

"""
seed_chroma.py — One-time script to embed fixture data into ChromaDB.

Run once before starting the Flask app:
    python scripts/seed_chroma.py

This script:
  1. Loads test_cases.json and defect_history.json from data/
  2. Embeds each item's descriptive text using nomic-embed-text via Ollama
  3. Upserts into ChromaDB collections 'test-case-index' and 'defect-history-index'
  4. Is idempotent — skips items already present in ChromaDB

Requirements:
  - Ollama must be running with nomic-embed-text pulled
  - .env must be configured (or CHROMA_DB_PATH env var set)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow imports from project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.utils.fixture_loader import load_fixture
from app.utils import llm_client, vector_store


def seed_test_cases() -> int:
    """Embed and upsert all test cases. Returns count of newly added items."""
    collection = "test-case-index"
    existing = vector_store.collection_count(collection)

    test_cases: list[dict] = load_fixture("test_cases")

    ids, docs, embeddings, metas = [], [], [], []
    for tc in test_cases:
        doc_id = tc["test_id"]
        # Build a rich description string for embedding
        text = (
            f"Test: {tc['test_name']}. "
            f"Module: {tc['module']}. "
            f"Journey: {tc.get('journey_id', '')}. "
            f"Description: {tc.get('description', '')}. "
            f"Browser: {tc['browser']}. Environment: {tc['environment']}."
        )
        ids.append(doc_id)
        docs.append(text)
        embeddings.append(llm_client.embed(text))
        metas.append({
            "test_id":    tc["test_id"],
            "test_name":  tc["test_name"],
            "module":     tc["module"],
            "journey_id": tc.get("journey_id", ""),
            "browser":    tc["browser"],
            "environment": tc["environment"],
            "last_run_status": tc.get("last_run_status", ""),
            "estimated_duration_s": tc.get("estimated_duration_s", 0),
            "coverage_fingerprint": tc.get("coverage_fingerprint", ""),
        })

    vector_store.upsert(collection, ids, docs, embeddings, metas)
    added = len(ids)
    print(f"  ✓ test-case-index: {added} items upserted ({existing} were already present)")
    return added


def seed_defect_history() -> int:
    """Embed and upsert defect history entries. Returns count of newly added items."""
    collection = "defect-history-index"
    existing = vector_store.collection_count(collection)

    defects: list[dict] = load_fixture("defect_history")

    ids, docs, embeddings, metas = [], [], [], []
    for dh in defects:
        doc_id = f"defect-{dh['module']}"
        text = (
            f"Module {dh['module']} has {dh['defect_count']} historical defects. "
            f"Critical: {dh['critical_defects']}, High: {dh['high_defects']}. "
            f"Average severity: {dh['severity_avg']}. "
            f"Recent commits: {dh['recent_commits']}. "
            f"Defect rate: {dh['defect_rate_per_kloc']} per KLOC. "
            f"Last defect: {dh.get('last_defect_date', 'unknown')}."
        )
        ids.append(doc_id)
        docs.append(text)
        embeddings.append(llm_client.embed(text))
        metas.append({
            "module":              dh["module"],
            "defect_count":        dh["defect_count"],
            "severity_avg":        dh["severity_avg"],
            "recent_commits":      dh["recent_commits"],
            "defect_rate_per_kloc": dh["defect_rate_per_kloc"],
        })

    vector_store.upsert(collection, ids, docs, embeddings, metas)
    added = len(ids)
    print(f"  ✓ defect-history-index: {added} items upserted ({existing} were already present)")
    return added


if __name__ == "__main__":
    print("Seeding ChromaDB from fixture files...")
    print(f"  Ollama URL:   {os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print(f"  ChromaDB path: {os.environ.get('CHROMA_DB_PATH', './chroma_db')}")
    print()

    try:
        seed_test_cases()
        seed_defect_history()
        print("\n✅ ChromaDB seeding complete.")
    except Exception as exc:
        print(f"\n❌ Seeding failed: {exc}")
        sys.exit(1)

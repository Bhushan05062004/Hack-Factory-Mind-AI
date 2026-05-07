"""
Factory Mind AI — SOP (Standard Operating Procedure) Embedding & Search
Indexes SOP documents with sentence-transformers (all-MiniLM-L6-v2).
FAISS index is persisted to disk.

TOKEN-EFFICIENCY: Limit top_k to 1 for SOPs; each snippet is trimmed
to <= 150 tokens before injection into the LLM prompt.
"""

import os
import json
import numpy as np
from typing import Optional

# Lazy-loaded globals
_model = None
_index = None
_sop_map: list[dict] = []

INDEX_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(INDEX_DIR, "sop_index.faiss")
MAP_PATH = os.path.join(INDEX_DIR, "sop_map.json")


def _get_model():
    """Lazy-load the sentence-transformer model (shared with products)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _sop_text(sop: dict) -> str:
    """Build the text string to embed for an SOP."""
    return f"{sop['title']} — {sop['content']}"


def build_sop_index() -> int:
    """
    Read all SOPs from SQLite, encode with sentence-transformers,
    and save a FAISS index to disk.
    Returns the number of SOPs indexed.
    """
    import faiss
    from db import get_all_sops

    sops = get_all_sops()
    if not sops:
        return 0

    model = _get_model()
    texts = [_sop_text(s) for s in sops]
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    os.makedirs(INDEX_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)

    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(sops, f, ensure_ascii=False, indent=2)

    return len(sops)


def _load_index():
    """Load FAISS index and SOP map from disk."""
    global _index, _sop_map
    if _index is not None:
        return

    import faiss

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            f"SOP FAISS index not found at {INDEX_PATH}. Run seed.py first."
        )

    _index = faiss.read_index(INDEX_PATH)
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        _sop_map = json.load(f)


def search_sops(query: str, k: int = 1) -> list[dict]:
    """
    Encode the query and search the FAISS index for the top-k
    most relevant SOP excerpts. Returns list of SOP dicts with
    a 'snippet' field trimmed to <= 150 tokens.
    """
    from utils import trim_to_tokens

    _load_index()

    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)
    query_vec = np.array(query_vec, dtype="float32")

    scores, indices = _index.search(query_vec, min(k, len(_sop_map)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_sop_map):
            continue
        sop = _sop_map[idx].copy()
        snippet = _sop_text(sop)
        sop["snippet"] = trim_to_tokens(snippet, max_tokens=150)
        sop["similarity_score"] = round(float(score), 4)
        results.append(sop)

    return results


def reload_index() -> None:
    """Force reload of the FAISS index."""
    global _index, _sop_map
    _index = None
    _sop_map = []
    _load_index()

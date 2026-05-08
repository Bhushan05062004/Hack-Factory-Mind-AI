"""
Factory Mind AI — SOP (Standard Operating Procedure) Embedding & Search
Uses Google Gemini Embedding API (zero local RAM) instead of sentence-transformers.
FAISS index is persisted to disk.

TOKEN-EFFICIENCY: Limit top_k to 1 for SOPs; each snippet is trimmed
to <= 150 tokens before injection into the LLM prompt.
"""

import os
import json
import numpy as np
from typing import Optional

# Lazy-loaded globals
_index = None
_sop_map: list[dict] = []

INDEX_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(INDEX_DIR, "sop_index.faiss")
MAP_PATH = os.path.join(INDEX_DIR, "sop_map.json")


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts using Google Gemini's free embedding API."""
    import google.generativeai as genai
    
    results = []
    for text in texts:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        results.append(result['embedding'])
    
    embeddings = np.array(results, dtype="float32")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    return embeddings


def _embed_query(query: str) -> np.ndarray:
    """Embed a single query using Google Gemini's free embedding API."""
    import google.generativeai as genai
    
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=query,
        task_type="RETRIEVAL_QUERY",
    )
    vec = np.array([result['embedding']], dtype="float32")
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vec = vec / norms
    return vec


def _sop_text(sop: dict) -> str:
    """Build the text string to embed for an SOP."""
    return f"{sop['title']} — {sop['content']}"


def build_sop_index() -> int:
    """
    Read all SOPs from SQLite, encode with Gemini embedding API,
    and save a FAISS index to disk.
    Returns the number of SOPs indexed.
    """
    import faiss
    from db import get_all_sops

    sops = get_all_sops()
    if not sops:
        return 0

    texts = [_sop_text(s) for s in sops]
    embeddings = _embed_texts(texts)

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

    query_vec = _embed_query(query)

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

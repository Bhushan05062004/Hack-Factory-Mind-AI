"""
Factory Mind AI — Product Catalog Embedding & FAISS Search
Uses Google Gemini Embedding API (zero local RAM) instead of sentence-transformers.
FAISS index is persisted to disk for fast startup.

TOKEN-EFFICIENCY: Limit top_k to 3 for products; each snippet is trimmed
to <= 120 tokens before injection into the LLM prompt.
"""

import os
import json
import numpy as np
from typing import Optional

# Lazy-loaded globals
_index = None
_product_map: list[dict] = []

INDEX_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(INDEX_DIR, "product_index.faiss")
MAP_PATH = os.path.join(INDEX_DIR, "product_map.json")

EMBED_DIM = 768  # Gemini embedding output dimension


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts using Google Gemini's free embedding API."""
    import google.generativeai as genai
    
    results = []
    # Process in batches of 20 to avoid rate limits
    for i in range(0, len(texts), 20):
        batch = texts[i:i+20]
        for text in batch:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="RETRIEVAL_DOCUMENT",
            )
            results.append(result['embedding'])
    
    embeddings = np.array(results, dtype="float32")
    # Normalize for cosine similarity
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


def _product_text(product: dict) -> str:
    """Build the text string to embed for a product."""
    return (
        f"Product ID: {product['id']} | "
        f"{product['name']} — {product['material']}, "
        f"{product['specification']}. "
        f"Part #{product['part_number']}. {product.get('description', '')}"
    )



def build_product_index() -> int:
    """
    Read all products from SQLite, encode descriptions with
    Gemini embedding API, and save a FAISS index to disk.
    Returns the number of products indexed.
    """
    import faiss
    from db import get_all_products

    products = get_all_products()
    if not products:
        return 0

    texts = [_product_text(p) for p in products]
    embeddings = _embed_texts(texts)

    # Inner-product index (cosine similarity on normalized vectors)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    os.makedirs(INDEX_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)

    # Save product metadata map
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    return len(products)


def _load_index():
    """Load FAISS index and product map from disk."""
    global _index, _product_map
    if _index is not None:
        return

    import faiss

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            f"Product FAISS index not found at {INDEX_PATH}. Run seed.py first."
        )

    _index = faiss.read_index(INDEX_PATH)
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        _product_map = json.load(f)


def search_products(query: str, k: int = 3) -> list[dict]:
    """
    Encode the query and search the FAISS index for the top-k
    most similar products. Returns list of product dicts with
    a 'snippet' field trimmed to <= 120 tokens.
    """
    from utils import trim_to_tokens

    _load_index()

    query_vec = _embed_query(query)

    scores, indices = _index.search(query_vec, min(k, len(_product_map)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_product_map):
            continue
        product = _product_map[idx].copy()
        snippet = _product_text(product)
        product["snippet"] = trim_to_tokens(snippet, max_tokens=120)
        product["similarity_score"] = round(float(score), 4)
        results.append(product)

    return results


def reload_index() -> None:
    """Force reload of the FAISS index (e.g., after adding new products)."""
    global _index, _product_map
    _index = None
    _product_map = []
    _load_index()

"""
Factory Mind AI — Product Catalog Embedding & FAISS Search
Indexes product descriptions with sentence-transformers (all-MiniLM-L6-v2).
FAISS index is persisted to disk for fast startup.

TOKEN-EFFICIENCY: Limit top_k to 3 for products; each snippet is trimmed
to <= 120 tokens before injection into the LLM prompt.
"""

import os
import json
import numpy as np
from typing import Optional

# Lazy-loaded globals
_model = None
_index = None
_product_map: list[dict] = []

INDEX_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(INDEX_DIR, "product_index.faiss")
MAP_PATH = os.path.join(INDEX_DIR, "product_map.json")


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


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
    sentence-transformers, and save a FAISS index to disk.
    Returns the number of products indexed.
    """
    import faiss
    from db import get_all_products

    products = get_all_products()
    if not products:
        return 0

    model = _get_model()
    texts = [_product_text(p) for p in products]
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")

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

    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)
    query_vec = np.array(query_vec, dtype="float32")

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

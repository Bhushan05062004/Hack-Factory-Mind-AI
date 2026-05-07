"""
Factory Mind AI — Utility Functions
Token counting, text trimming, datetime helpers.
"""

from datetime import datetime


def estimate_tokens(text: str) -> int:
    """
    Approximate token count using the ~4 chars per token heuristic.
    For precise counts, use tiktoken or the model's tokenizer,
    but this is sufficient for budget estimation.
    """
    return max(1, len(text) // 4)


def trim_to_tokens(text: str, max_tokens: int = 120) -> str:
    """
    Trim text to approximately max_tokens.
    Cuts at word boundaries to avoid partial words.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    # Cut at last space to avoid partial words
    last_space = trimmed.rfind(" ")
    if last_space > max_chars // 2:
        trimmed = trimmed[:last_space]
    return trimmed.rstrip() + "..."


def now_iso() -> str:
    """Return current UTC time as ISO-formatted string."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def format_order_summary(order: dict) -> str:
    """Format an order dict into a human-readable summary string."""
    return (
        f"Order #{order['id']} — {order['part_name']} "
        f"({order['material']}) | Qty: {order['quantity']} | "
        f"Deadline: {order['deadline']} | Status: {order['status']}"
    )

"""
Factory Mind AI — SQLite Database Layer
All tables, CRUD helpers, and connection management.
Uses parameterised queries exclusively for SQL-injection safety.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "factory_mind_ai.db"))


def _ensure_dir() -> None:
    """Create the data directory if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row-factory enabled."""
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        email       TEXT    UNIQUE NOT NULL,
        name        TEXT    NOT NULL,
        password    TEXT    NOT NULL,
        role        TEXT    NOT NULL CHECK(role IN ('user','operator','quality'))
    );

    CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT    UNIQUE NOT NULL,
        name        TEXT    NOT NULL,
        material    TEXT    NOT NULL,
        specification TEXT  NOT NULL DEFAULT '',
        description TEXT    NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS sops (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        content     TEXT    NOT NULL,
        category    TEXT    NOT NULL DEFAULT 'general'
    );

    CREATE TABLE IF NOT EXISTS orders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id             INTEGER NOT NULL,
        product_id          INTEGER,
        part_name           TEXT    NOT NULL,
        material            TEXT    NOT NULL DEFAULT 'Not specified',
        specification       TEXT    NOT NULL DEFAULT '',
        quantity            INTEGER NOT NULL CHECK(quantity > 0),
        deadline            TEXT    NOT NULL,
        notes               TEXT    NOT NULL DEFAULT '',
        status              TEXT    NOT NULL DEFAULT 'Received'
                            CHECK(status IN ('Received','In Review','Accepted','Cancelled')),
        last_quality_note   TEXT,
        last_quality_ts     TEXT,
        created_at          TEXT    NOT NULL,
        cancellable_until   TEXT    NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS quality_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id    INTEGER NOT NULL,
        note        TEXT    NOT NULL,
        logged_by   INTEGER,
        timestamp   TEXT    NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (logged_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS usage (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        in_tokens   INTEGER NOT NULL DEFAULT 0,
        out_tokens  INTEGER NOT NULL DEFAULT 0
    );
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  USER HELPERS
# ─────────────────────────────────────────────
def get_user_by_email(email: str) -> Optional[dict]:
    """Look up a user by email. Returns dict or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Look up a user by ID. Returns dict or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

import hashlib

def hash_password(password: str) -> str:
    """Return a SHA-256 hash of the password."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against the hashed version."""
    return hash_password(plain) == hashed

def register_user(email: str, name: str, password: str, role: str = "user") -> Optional[dict]:
    """Register a new user with a hashed password."""
    conn = get_connection()
    hashed = hash_password(password)
    try:
        cur = conn.execute(
            "INSERT INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
            (email, name, hashed, role)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        conn.close()
        return None  # Email already exists

# ─────────────────────────────────────────────
#  PRODUCT HELPERS
# ─────────────────────────────────────────────
def get_all_products() -> list[dict]:
    """Return every product as a dict."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_by_id(product_id: int) -> Optional[dict]:
    """Return a single product by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# ─────────────────────────────────────────────
#  SOP HELPERS
# ─────────────────────────────────────────────
def get_all_sops() -> list[dict]:
    """Return every SOP document as a dict."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sops ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  ORDER HELPERS
# ─────────────────────────────────────────────
def create_order(
    user_id: int,
    part_name: str,
    quantity: int,
    deadline: str,
    material: str = "Not specified",
    specification: str = "",
    notes: str = "",
    product_id: Optional[int] = None,
) -> dict:
    """Insert a new order with status='Received' and 4-day cancellation window."""
    now = datetime.utcnow()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    cancellable_until = (now + timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO orders
           (user_id, product_id, part_name, material, specification, quantity,
            deadline, notes, status, created_at, cancellable_until)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Received', ?, ?)""",
        (user_id, product_id, part_name, material, specification,
         quantity, deadline, notes, created_at, cancellable_until),
    )
    order_id = cur.lastrowid
    conn.commit()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(order)


def get_order(order_id: int) -> Optional[dict]:
    """Return a single order by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def update_order_status(order_id: int, new_status: str) -> Optional[dict]:
    """Update an order's status. Returns updated order or None if not found."""
    conn = get_connection()
    conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (new_status, order_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def query_orders(
    status: Optional[str] = None,
    limit: int = 10,
    user_id: Optional[int] = None,
    role: str = "user",
) -> list[dict]:
    """
    Return a filtered list of orders.
    Normal users cannot see orders with status='Accepted' (internal).
    user_id filter is applied for normal users (they only see their own).
    """
    conn = get_connection()
    query = "SELECT * FROM orders WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)

    # RBAC: normal users only see their own orders
    if role == "user" and user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    # RBAC: normal users cannot see Accepted status
    if role == "user":
        query += " AND status != 'Accepted'"

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        # RBAC: hide quality notes from normal users
        if role == "user":
            d.pop("last_quality_note", None)
            d.pop("last_quality_ts", None)
        results.append(d)
    return results


def cancel_order(order_id: int) -> tuple[bool, str]:
    """
    Cancel an order if within the cancellable_until window.
    Returns (success: bool, message: str).
    """
    order = get_order(order_id)
    if not order:
        return False, f"Order #{order_id} not found."

    if order["status"] == "Cancelled":
        return False, f"Order #{order_id} is already cancelled."

    now = datetime.utcnow()
    cancel_deadline = datetime.strptime(order["cancellable_until"], "%Y-%m-%d %H:%M:%S")
    if now > cancel_deadline:
        return False, (
            f"Cancellation window for Order #{order_id} has expired. "
            f"The deadline was {order['cancellable_until']}."
        )

    update_order_status(order_id, "Cancelled")
    return True, f"Order #{order_id} has been cancelled successfully."


# ─────────────────────────────────────────────
#  QUALITY LOG HELPERS
# ─────────────────────────────────────────────
def log_quality(order_id: int, note: str, logged_by: Optional[int] = None) -> Optional[dict]:
    """
    Append a quality-inspection note to an order.
    Updates order's last_quality_note and last_quality_ts.
    """
    order = get_order(order_id)
    if not order:
        return None

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute(
        "INSERT INTO quality_logs (order_id, note, logged_by, timestamp) VALUES (?, ?, ?, ?)",
        (order_id, note, logged_by, now),
    )
    conn.execute(
        "UPDATE orders SET last_quality_note = ?, last_quality_ts = ? WHERE id = ?",
        (note, now, order_id),
    )
    conn.commit()
    conn.close()
    return {"order_id": order_id, "note": note, "timestamp": now}


def get_quality_logs(order_id: int) -> list[dict]:
    """Return all quality logs for a given order."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM quality_logs WHERE order_id = ? ORDER BY timestamp",
        (order_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  TOKEN USAGE HELPERS
# ─────────────────────────────────────────────
def log_usage(in_tokens: int, out_tokens: int) -> None:
    """Record a single LLM call's token usage."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute(
        "INSERT INTO usage (timestamp, in_tokens, out_tokens) VALUES (?, ?, ?)",
        (now, in_tokens, out_tokens),
    )
    conn.commit()
    conn.close()


def get_cumulative_usage() -> dict:
    """Return cumulative token usage and estimated cost."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(in_tokens),0) as total_in, "
        "COALESCE(SUM(out_tokens),0) as total_out, "
        "COUNT(*) as total_calls FROM usage"
    ).fetchone()
    conn.close()

    total_in = row["total_in"]
    total_out = row["total_out"]
    # Gemini pricing approximation (adjust as needed)
    # Gemini Flash: ~$0.075/1M input, ~$0.30/1M output
    cost_in = (total_in / 1_000_000) * 0.075
    cost_out = (total_out / 1_000_000) * 0.30
    return {
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "total_calls": row["total_calls"],
        "estimated_cost_usd": round(cost_in + cost_out, 6),
    }

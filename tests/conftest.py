"""
Factory Mind AI — Test Fixtures
Provides TestClient, seeded database, and auth tokens for each role.
"""

import os
import sys
import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Use a test database
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "test_data", "test.db")
os.environ["JWT_SECRET"] = "test-secret"
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "test-key")

from db import init_db, get_connection


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create tables and seed minimal test data."""
    # Ensure test data directory exists
    os.makedirs(os.path.join(os.path.dirname(__file__), "test_data"), exist_ok=True)

    # Remove old test DB if present
    db_path = os.environ["DB_PATH"]
    if os.path.exists(db_path):
        os.remove(db_path)

    init_db()

    conn = get_connection()
    cur = conn.cursor()

    # Seed test users
    cur.execute("INSERT INTO users (email, name, role) VALUES (?, ?, ?)", ("alice@test.com", "Alice", "user"))
    cur.execute("INSERT INTO users (email, name, role) VALUES (?, ?, ?)", ("bob@test.com", "Bob", "operator"))
    cur.execute("INSERT INTO users (email, name, role) VALUES (?, ?, ?)", ("carol@test.com", "Carol", "quality"))

    # Seed test products
    cur.execute(
        "INSERT INTO products (part_number, name, material, specification, description) VALUES (?, ?, ?, ?, ?)",
        ("TF-80-A", "Titanium Flange", "Titanium Grade 5", "Aerospace grade, 80 mm bore", "High-strength titanium flange"),
    )
    cur.execute(
        "INSERT INTO products (part_number, name, material, specification, description) VALUES (?, ?, ?, ?, ?)",
        ("SB-M10-SS", "Steel Bracket", "Stainless Steel 316L", "M10 mounting", "Heavy-duty stainless steel bracket"),
    )

    # Seed test SOPs
    cur.execute(
        "INSERT INTO sops (title, content, category) VALUES (?, ?, ?)",
        ("Flange Inspection Procedure", "1. Visual check. 2. Dimensional check. 3. Pressure test.", "inspection"),
    )

    conn.commit()
    conn.close()

    yield

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client():
    """FastAPI test client using Starlette TestClient (synchronous)."""
    from starlette.testclient import TestClient
    from app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_token(client):
    """Get JWT for user role."""
    res = client.post("/login", json={"email": "alice@test.com"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def operator_token(client):
    """Get JWT for operator role."""
    res = client.post("/login", json={"email": "bob@test.com"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def quality_token(client):
    """Get JWT for quality role."""
    res = client.post("/login", json={"email": "carol@test.com"})
    assert res.status_code == 200
    return res.json()["access_token"]

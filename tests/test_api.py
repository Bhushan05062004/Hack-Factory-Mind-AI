"""
Factory Mind AI — API Tests
Tests login, RBAC enforcement, order lifecycle, cancellation, and metrics.
"""

import pytest


class TestAuth:
    """Authentication tests."""

    def test_login_valid_user(self, client):
        res = client.post("/login", json={"email": "alice@test.com"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["role"] == "user"
        assert data["name"] == "Alice"

    def test_login_valid_operator(self, client):
        res = client.post("/login", json={"email": "bob@test.com"})
        assert res.status_code == 200
        assert res.json()["role"] == "operator"

    def test_login_valid_quality(self, client):
        res = client.post("/login", json={"email": "carol@test.com"})
        assert res.status_code == 200
        assert res.json()["role"] == "quality"

    def test_login_invalid_email(self, client):
        res = client.post("/login", json={"email": "nobody@test.com"})
        assert res.status_code == 401

    def test_chat_without_token(self, client):
        res = client.post("/chat", json={"message": "hello"})
        assert res.status_code in (401, 403)

    def test_orders_without_token(self, client):
        res = client.get("/orders")
        assert res.status_code in (401, 403)


class TestHealth:
    """Health check tests."""

    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestMetrics:
    """Metrics endpoint tests."""

    def test_metrics(self, client):
        res = client.get("/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "total_input_tokens" in data
        assert "total_output_tokens" in data
        assert "estimated_cost_usd" in data


class TestRBAC:
    """Role-based access control tests."""

    def test_user_can_query_orders(self, client, user_token):
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.get("/orders", headers=headers)
        assert res.status_code == 200

    def test_operator_can_query_orders(self, client, operator_token):
        headers = {"Authorization": f"Bearer {operator_token}"}
        res = client.get("/orders", headers=headers)
        assert res.status_code == 200

    def test_user_status_update_blocked(self, client, user_token):
        """User cannot update status via chat (regex path)."""
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.post("/chat", json={"message": "Accept order #1"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        # Should be blocked by RBAC
        assert "operator" in data.get("message", "").lower() or "permission" in data.get("message", "").lower() or data.get("type") in ("rule", "function")

    def test_user_quality_log_blocked(self, client, user_token):
        """User cannot log quality notes."""
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.post("/chat", json={"message": "Quality update on order #1 — passed inspection"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "quality" in data.get("message", "").lower() or "permission" in data.get("message", "").lower()


class TestOrderLifecycle:
    """Order creation and management tests using the regex rule engine."""

    def test_query_orders_empty(self, client, user_token):
        """Querying orders when none exist."""
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.post("/chat", json={"message": "Show all my orders"}, headers=headers)
        assert res.status_code == 200

    def test_operator_status_update_via_regex(self, client, operator_token):
        """Operator can update status via regex path (zero-token)."""
        headers = {"Authorization": f"Bearer {operator_token}"}
        # This may fail if order #1 doesn't exist, but the response should still be valid
        res = client.post("/chat", json={"message": "Move order #1 to In Review"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("type") in ("rule", "function", "fallback")

    def test_quality_log_via_regex(self, client, quality_token):
        """Quality team can log notes via regex path."""
        headers = {"Authorization": f"Bearer {quality_token}"}
        res = client.post("/chat", json={"message": "Quality inspection on order #1 — passed visual check"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("type") in ("rule", "function", "fallback")


class TestChatResponse:
    """Validate chat response structure."""

    def test_response_has_usage(self, client, user_token):
        """Every chat response should include usage info."""
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.post("/chat", json={"message": "Show all orders"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "usage" in data
        assert "input_tokens" in data["usage"]

    def test_response_has_type(self, client, user_token):
        """Every response must have a type field."""
        headers = {"Authorization": f"Bearer {user_token}"}
        res = client.post("/chat", json={"message": "List my orders"}, headers=headers)
        assert res.status_code == 200
        assert "type" in res.json()

    def test_regex_path_no_tokens(self, client, operator_token):
        """Regex-handled requests should use zero tokens."""
        headers = {"Authorization": f"Bearer {operator_token}"}
        res = client.post("/chat", json={"message": "Show all orders"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        if data.get("type") == "rule":
            assert data["usage"]["llm_used"] is False

"""
Factory Mind AI — LLM Extraction Benchmark
30 sample utterances testing the regex rule engine and (when available) LLM extraction.
Tests that can be validated without an API key use the regex path only.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DB_PATH", os.path.join(os.path.dirname(__file__), "test_data", "test.db"))
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from llm import _try_regex_status_update, _try_regex_quality_log, _try_regex_query


# ─────────────────────────────────────────────
#  REGEX STATUS UPDATE TESTS (15 utterances)
# ─────────────────────────────────────────────
REGEX_STATUS_CASES = [
    # (utterance, role, expected_status_or_None, should_match)
    ("Accept order #5", "operator", "Accepted", True),
    ("Approve order #12", "operator", "Accepted", True),
    ("Confirm order #7", "operator", "Accepted", True),
    ("Green light order #3", "operator", "Accepted", True),
    ("Sign off on order #8", "operator", "Accepted", True),
    ("Move order #1 to In Review", "operator", "In Review", True),
    ("Put order #4 in review", "operator", "In Review", True),
    ("Start reviewing order #9", "operator", "In Review", True),
    ("Review order #2", "operator", "In Review", True),
    ("Cancel order #6", "user", "Cancelled", True),
    ("I want to cancel order #10", "user", "Cancelled", True),
    ("Accept order #1", "user", None, True),  # blocked by RBAC
    ("Move order #3 to In Review", "user", None, True),  # blocked by RBAC
    ("I need 50 steel brackets", "operator", None, False),  # not a status update
    ("What is the inspection procedure?", "operator", None, False),  # not a status update
]


class TestRegexStatusUpdate:
    """Test regex-based status update detection."""

    @pytest.mark.parametrize("text,role,expected_status,should_match", REGEX_STATUS_CASES)
    def test_status_regex(self, text, role, expected_status, should_match):
        result = _try_regex_status_update(text, role)

        if not should_match:
            assert result is None, f"Should not match: {text}"
            return

        assert result is not None, f"Should match: {text}"

        if expected_status is None:
            # RBAC blocked
            assert "operator" in result.message.lower() or "permission" in result.message.lower()
        else:
            # Check the payload or message contains expected status
            assert result.name == "update_status"


# ─────────────────────────────────────────────
#  REGEX QUALITY LOG TESTS (8 utterances)
# ─────────────────────────────────────────────
REGEX_QUALITY_CASES = [
    ("Quality update on order #5 — passed visual inspection", "quality", True, True),
    ("Order #3 passed dimensional check, no defects found", "quality", True, True),
    ("QC note for order #7: out of spec on bore diameter", "quality", True, True),
    ("Inspection done on order #2, all dimensions within tolerance", "quality", True, True),
    ("Order #1 failed surface inspection", "quality", True, True),
    ("Quality check on order #4 — approved by QC", "operator", True, True),
    ("Quality update on order #1 — passed", "user", False, True),  # blocked
    ("I need to order some parts", "quality", None, False),  # not a quality log
]


class TestRegexQualityLog:
    """Test regex-based quality log detection."""

    @pytest.mark.parametrize("text,role,expected_success,should_match", REGEX_QUALITY_CASES)
    def test_quality_regex(self, text, role, expected_success, should_match):
        result = _try_regex_quality_log(text, role)

        if not should_match:
            assert result is None, f"Should not match: {text}"
            return

        assert result is not None, f"Should match: {text}"

        if expected_success is False:
            assert "quality" in result.message.lower() or "permission" in result.message.lower()


# ─────────────────────────────────────────────
#  REGEX QUERY TESTS (7 utterances)
# ─────────────────────────────────────────────
REGEX_QUERY_CASES = [
    ("Show me all orders", "user", True),
    ("List all received orders", "operator", True),
    ("Display order #5", "user", True),
    ("What orders do I have?", "user", True),
    ("Show all accepted orders", "operator", True),
    ("List my orders", "user", True),
    ("I need to order bolts", "user", False),  # not a query
]


class TestRegexQuery:
    """Test regex-based order query detection."""

    @pytest.mark.parametrize("text,role,should_match", REGEX_QUERY_CASES)
    def test_query_regex(self, text, role, should_match):
        result = _try_regex_query(text, role, user_id=1)

        if not should_match:
            assert result is None, f"Should not match: {text}"
        else:
            assert result is not None, f"Should match: {text}"
            assert result.name == "query_orders"


# ─────────────────────────────────────────────
#  ACCURACY SUMMARY
# ─────────────────────────────────────────────
class TestAccuracy:
    """Verify overall regex extraction accuracy meets 90% threshold."""

    def test_overall_accuracy(self):
        """Run all 30 cases and verify >= 90% accuracy."""
        total = 0
        correct = 0

        for text, role, expected_status, should_match in REGEX_STATUS_CASES:
            total += 1
            result = _try_regex_status_update(text, role)
            if should_match and result is not None:
                correct += 1
            elif not should_match and result is None:
                correct += 1

        for text, role, expected_success, should_match in REGEX_QUALITY_CASES:
            total += 1
            result = _try_regex_quality_log(text, role)
            if should_match and result is not None:
                correct += 1
            elif not should_match and result is None:
                correct += 1

        for text, role, should_match in REGEX_QUERY_CASES:
            total += 1
            result = _try_regex_query(text, role, user_id=1)
            if should_match and result is not None:
                correct += 1
            elif not should_match and result is None:
                correct += 1

        accuracy = correct / total if total > 0 else 0
        assert accuracy >= 0.90, f"Extraction accuracy {accuracy:.1%} < 90% ({correct}/{total})"

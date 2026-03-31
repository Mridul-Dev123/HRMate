"""
Unit tests for db_utils.py
"""
import sqlite3
import pytest
from db_utils import init_db, log_interaction, get_pto_balance, submit_leave_request


# ── Table creation ────────────────────────────────────────────────────────

class TestInitDb:
    def test_creates_analytics_table(self, tmp_db):
        init_db()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_employees_table(self, tmp_db):
        init_db()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_leave_requests_table(self, tmp_db):
        init_db()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leave_requests'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_seeds_mock_employees(self, tmp_db):
        init_db()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        conn.close()
        assert count >= 2  # default user + test user

    def test_idempotent_seed(self, tmp_db):
        """Calling init_db() twice should not duplicate seed data."""
        init_db()
        init_db()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 2


# ── log_interaction ───────────────────────────────────────────────────────

class TestLogInteraction:
    def test_inserts_row(self, initialized_db):
        log_interaction("alice@example.com", "How many days off?", "You have 15 days.")
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT * FROM analytics")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][2] == "alice@example.com"

    def test_multiple_logs(self, initialized_db):
        log_interaction("a@b.com", "Q1", "A1")
        log_interaction("c@d.com", "Q2", "A2")
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT COUNT(*) FROM analytics")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 2


# ── get_pto_balance ───────────────────────────────────────────────────────

class TestGetPtoBalance:
    def test_existing_employee(self, initialized_db):
        result = get_pto_balance("mridul@example.com")
        assert "20" in result
        assert "mridul@example.com" in result

    def test_missing_employee(self, initialized_db):
        result = get_pto_balance("nobody@example.com")
        assert "could not find" in result.lower()


# ── submit_leave_request ──────────────────────────────────────────────────

class TestSubmitLeaveRequest:
    def test_success(self, initialized_db):
        result = submit_leave_request("mridul@example.com", "2024-10-01", "2024-10-05")
        assert "successfully submitted" in result.lower()
        # Verify it's in the DB
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT * FROM leave_requests WHERE email='mridul@example.com'")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[4] == "PENDING"

    def test_missing_employee(self, initialized_db):
        result = submit_leave_request("ghost@example.com", "2024-01-01", "2024-01-02")
        assert "could not find" in result.lower()

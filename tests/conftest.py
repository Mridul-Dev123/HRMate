"""
Shared pytest fixtures for HRMate test suite.
"""
import os
import sys
import sqlite3
import pytest

# Ensure the project root is on the path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """
    Creates a temporary SQLite database for each test.
    Monkeypatches db_utils.DB_FILE so all DB calls go to the temp file.
    """
    db_file = str(tmp_path / "test_hr.db")
    monkeypatch.setattr("db_utils.DB_FILE", db_file)
    return db_file


@pytest.fixture
def initialized_db(tmp_db):
    """
    Returns a tmp_db that has already been initialised via init_db().
    """
    from db_utils import init_db
    init_db()
    return tmp_db

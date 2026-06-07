import sqlite3
import pytest
from web_app.db import get_db, init_db


def test_init_db_creates_messages_table(app):
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        assert cursor.fetchone() is not None


def test_init_db_creates_templates_table(app):
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='msg_templates'"
        )
        assert cursor.fetchone() is not None


def test_init_db_preserves_contacts_table(app):
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
        )
        assert cursor.fetchone() is not None


def test_get_db_returns_same_connection_within_context(app):
    with app.app_context():
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2


def test_messages_table_has_correct_columns(app):
    with app.app_context():
        db = get_db()
        cursor = db.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == {'id', 'recipients', 'message', 'sent_at', 'status', 'error'}


def test_templates_table_has_correct_columns(app):
    with app.app_context():
        db = get_db()
        cursor = db.execute("PRAGMA table_info(msg_templates)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == {'id', 'name', 'body_markdown', 'created_at', 'updated_at'}

import pytest
import tempfile
import os
import sys
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from web_app.app import create_app
from web_app.db import init_db, get_db

TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'test-password-1234'


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret',
        'ENV_FILE': None,
        'WTF_CSRF_ENABLED': False,
    })
    with app.app_context():
        init_db()
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def seed_user(app, username=TEST_USERNAME, password=TEST_PASSWORD):
    """Insert a user directly into the DB and return its id."""
    with app.app_context():
        db = get_db()
        cur = db.execute(
            'INSERT INTO users (username, password_hash, created_at, failed_attempts) '
            'VALUES (?, ?, ?, 0)',
            (username, generate_password_hash(password), datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        return cur.lastrowid


@pytest.fixture
def auth_client(app):
    user_id = seed_user(app)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = TEST_USERNAME
    return client

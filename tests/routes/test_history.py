import json
from datetime import datetime, timezone
from web_app.db import get_db


def _insert_message(app, recipients, message, status='sent', error=None):
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO messages (recipients, message, sent_at, status, error) VALUES (?, ?, ?, ?, ?)',
            (json.dumps(recipients), message, datetime.now(timezone.utc).isoformat(), status, error)
        )
        db.commit()


def test_history_page_loads(auth_client):
    response = auth_client.get('/history/')
    assert response.status_code == 200


def test_history_shows_sent_message(auth_client, app):
    _insert_message(app, ['+15551234567'], 'Test message')
    response = auth_client.get('/history/')
    assert b'Test message' in response.data


def test_history_shows_status(auth_client, app):
    _insert_message(app, ['+15551234567'], 'Good msg', status='sent')
    _insert_message(app, ['+15559876543'], 'Bad msg', status='failed', error='timeout')
    response = auth_client.get('/history/')
    assert b'sent' in response.data
    assert b'failed' in response.data


def test_history_filter_by_status(auth_client, app):
    _insert_message(app, ['+15551234567'], 'Only sent', status='sent')
    _insert_message(app, ['+15559876543'], 'Only failed', status='failed')
    response = auth_client.get('/history/?status=failed')
    assert b'Only failed' in response.data
    assert b'Only sent' not in response.data


def test_history_newest_first(auth_client, app):
    import time
    _insert_message(app, ['+15551111111'], 'First message')
    time.sleep(0.01)
    _insert_message(app, ['+15552222222'], 'Second message')
    response = auth_client.get('/history/')
    content = response.data.decode()
    assert content.index('Second message') < content.index('First message')

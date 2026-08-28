import json
from unittest.mock import patch
from datetime import datetime, timezone


def _add_contact(auth_client, name, phone, group=''):
    auth_client.post('/contacts/add', data={'name': name, 'phone': phone, 'group_name': group})


def test_send_page_loads(auth_client):
    response = auth_client.get('/send/')
    assert response.status_code == 200


def test_send_page_shows_contacts(auth_client):
    _add_contact(auth_client, 'Alice', '5551234567')
    response = auth_client.get('/send/')
    assert b'Alice' in response.data


_FAKE_ENV = {'TEXTBEE_API_KEY': 'test-key', 'TEXTBEE_DEVICE_ID': 'test-device'}


def test_send_to_individual_success(auth_client, app):
    _add_contact(auth_client, 'Bob', '5559876543')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Bob'").fetchone()[0]

    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result), \
         patch('web_app.routes.send._read_env', return_value=_FAKE_ENV):
        response = auth_client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Hello Bob!',
        }, follow_redirects=True)
    assert response.status_code == 200
    assert b'sent' in response.data.lower() or b'success' in response.data.lower()


def test_send_logs_to_history(auth_client, app):
    _add_contact(auth_client, 'Carol', '5553334444')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Carol'").fetchone()[0]

    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result), \
         patch('web_app.routes.send._read_env', return_value=_FAKE_ENV):
        auth_client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Logged message',
        })

    with app.app_context():
        from web_app.db import get_db
        row = get_db().execute("SELECT * FROM messages WHERE message='Logged message'").fetchone()
    assert row is not None
    assert row['status'] == 'sent'


def test_send_logs_failure(auth_client, app):
    _add_contact(auth_client, 'Dave', '5550001111')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Dave'").fetchone()[0]

    mock_result = {'success': False, 'error': 'timeout'}
    with patch('web_app.routes.send.send_sms', return_value=mock_result), \
         patch('web_app.routes.send._read_env', return_value=_FAKE_ENV):
        auth_client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Will fail',
        })

    with app.app_context():
        from web_app.db import get_db
        row = get_db().execute("SELECT * FROM messages WHERE message='Will fail'").fetchone()
    assert row['status'] == 'failed'
    assert 'timeout' in row['error']


def test_send_to_manual_number(auth_client):
    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result), \
         patch('web_app.routes.send._read_env', return_value=_FAKE_ENV):
        response = auth_client.post('/send/', data={
            'recipient_type': 'manual',
            'manual_phone': '5557778888',
            'message': 'Manual send',
        }, follow_redirects=True)
    assert response.status_code == 200


def test_send_empty_message_rejected(auth_client):
    response = auth_client.post('/send/', data={
        'recipient_type': 'manual',
        'manual_phone': '5557778888',
        'message': '',
    }, follow_redirects=True)
    assert b'Message cannot be empty' in response.data

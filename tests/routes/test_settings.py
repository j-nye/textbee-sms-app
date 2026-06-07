import os
import tempfile
import pytest
from web_app.app import create_app
from web_app.db import init_db


@pytest.fixture
def app_with_env(tmp_path):
    db_fd, db_path = tempfile.mkstemp()
    env_path = str(tmp_path / '.env')
    with open(env_path, 'w') as f:
        f.write('TEXTBEE_API_KEY=test-key\nTEXTBEE_DEVICE_ID=test-device\n')
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test',
        'ENV_FILE': env_path,
    })
    with app.app_context():
        init_db()
    yield app, env_path
    os.close(db_fd)
    os.unlink(db_path)


def test_settings_page_loads(client):
    response = client.get('/settings/')
    assert response.status_code == 200


def test_settings_shows_existing_credentials(app_with_env):
    app, env_path = app_with_env
    client = app.test_client()
    response = client.get('/settings/')
    assert b'test-key' in response.data
    assert b'test-device' in response.data


def test_settings_save_updates_env_file(app_with_env):
    app, env_path = app_with_env
    client = app.test_client()
    response = client.post('/settings/', data={
        'api_key': 'new-api-key',
        'device_id': 'new-device-id',
    }, follow_redirects=True)
    assert response.status_code == 200
    with open(env_path) as f:
        content = f.read()
    assert 'new-api-key' in content
    assert 'new-device-id' in content

import os
import tempfile
import pytest
from web_app.app import create_app
from web_app.db import init_db
from tests.conftest import seed_user


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
        'WTF_CSRF_ENABLED': False,
    })
    with app.app_context():
        init_db()
    yield app, env_path
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def auth_client_with_env(app_with_env):
    app, env_path = app_with_env
    user_id = seed_user(app)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return client, env_path


def test_settings_page_loads(auth_client):
    response = auth_client.get('/settings/')
    assert response.status_code == 200


def test_settings_shows_existing_credentials(auth_client_with_env):
    client, env_path = auth_client_with_env
    response = client.get('/settings/')
    assert b'test-key' in response.data
    assert b'test-device' in response.data


def test_settings_save_updates_env_file(auth_client_with_env):
    client, env_path = auth_client_with_env
    response = client.post('/settings/', data={
        'api_key': 'new-api-key',
        'device_id': 'new-device-id',
    }, follow_redirects=True)
    assert response.status_code == 200
    with open(env_path) as f:
        content = f.read()
    assert 'new-api-key' in content
    assert 'new-device-id' in content


def test_google_connect_requires_base_url(auth_client_with_env, tmp_path):
    client, env_path = auth_client_with_env
    secret_file = tmp_path / 'client_secret.json'
    secret_file.write_text('{}')
    with open(env_path, 'a') as f:
        f.write(f'GOOGLE_CLIENT_SECRET_FILE={secret_file}\n')

    response = client.get('/settings/google/connect', follow_redirects=True)

    assert response.status_code == 200
    assert b'Public Base URL' in response.data


def test_google_connect_builds_redirect_from_configured_base_url(auth_client_with_env, tmp_path, monkeypatch):
    client, env_path = auth_client_with_env
    secret_file = tmp_path / 'client_secret.json'
    secret_file.write_text('{}')
    with open(env_path, 'a') as f:
        f.write(f'GOOGLE_CLIENT_SECRET_FILE={secret_file}\n')
        f.write('APP_BASE_URL=https://sms.example.com\n')

    captured = {}

    def fake_start_oauth_flow(client_secret_file, redirect_uri):
        captured['redirect_uri'] = redirect_uri
        return 'https://accounts.google.com/o/oauth2/auth?fake=1', 'fake-state', object()

    monkeypatch.setattr('web_app.google_sync.start_oauth_flow', fake_start_oauth_flow)

    # Werkzeug's test client models real browser cookie-domain scoping: a
    # session cookie set for 'localhost' is not attached to a request whose
    # Host header says 'evil.example.com', so the login-required gate would
    # otherwise redirect to /login before this view ever runs. A raw HTTP
    # client forging the Host header (the actual attack this test targets)
    # isn't bound by that browser policy, so re-register the same session
    # cookie under the spoofed host to reach the view under test.
    session_cookie = client.get_cookie('session', domain='localhost')
    client.set_cookie(domain='evil.example.com', key='session', value=session_cookie.value)

    response = client.get('/settings/google/connect', headers={'Host': 'evil.example.com'})

    assert response.status_code == 302
    assert captured['redirect_uri'] == 'https://sms.example.com/settings/google/callback'


def test_google_callback_requires_base_url(auth_client_with_env, tmp_path):
    client, env_path = auth_client_with_env
    secret_file = tmp_path / 'client_secret.json'
    secret_file.write_text('{}')
    with client.session_transaction() as sess:
        sess['google_oauth_state'] = 'fake-state'
        sess['google_client_secret_file'] = str(secret_file)

    response = client.get('/settings/google/callback?state=fake-state&code=abc', follow_redirects=True)

    assert response.status_code == 200
    assert b'OAuth session expired' in response.data


def test_settings_save_persists_base_url(auth_client_with_env):
    client, env_path = auth_client_with_env
    response = client.post('/settings/', data={
        'api_key': 'k',
        'device_id': 'd',
        'app_base_url': 'https://sms.example.com',
    }, follow_redirects=True)
    assert response.status_code == 200
    with open(env_path) as f:
        content = f.read()
    assert 'APP_BASE_URL=https://sms.example.com' in content

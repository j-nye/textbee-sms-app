import tempfile
import os
from datetime import datetime, timedelta, timezone
import pytest
from web_app.app import create_app
from web_app.db import get_db, init_db
from web_app.routes.auth import GENERIC_LOGIN_ERROR
from tests.conftest import seed_user, TEST_USERNAME, TEST_PASSWORD


@pytest.fixture
def csrf_client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret',
        'ENV_FILE': None,
        'WTF_CSRF_ENABLED': True,
    })
    with app.app_context():
        init_db()
    yield app.test_client()
    os.close(db_fd)
    os.unlink(db_path)


def test_setup_shown_when_no_user(client):
    response = client.get('/setup')
    assert response.status_code == 200
    assert b'Create' in response.data


def test_setup_creates_user_and_logs_in(client, app):
    response = client.post('/setup', data={
        'username': 'alice',
        'password': 'a-very-long-password',
        'confirm_password': 'a-very-long-password',
    })
    assert response.status_code == 302
    assert response.headers['Location'] == '/send/'
    with app.app_context():
        row = get_db().execute('SELECT * FROM users').fetchone()
        assert row['username'] == 'alice'
    with client.session_transaction() as sess:
        assert sess['user_id'] == row['id']


def test_setup_rejects_short_password(client, app):
    client.post('/setup', data={
        'username': 'alice',
        'password': 'short',
        'confirm_password': 'short',
    })
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) c FROM users').fetchone()['c'] == 0


def test_setup_rejects_mismatched_confirmation(client, app):
    client.post('/setup', data={
        'username': 'alice',
        'password': 'a-very-long-password',
        'confirm_password': 'a-different-password',
    })
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) c FROM users').fetchone()['c'] == 0


def test_setup_redirects_to_login_when_user_exists(client, app):
    seed_user(app)
    response = client.get('/setup')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

    response = client.post('/setup', data={
        'username': 'second',
        'password': 'a-very-long-password',
        'confirm_password': 'a-very-long-password',
    })
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) c FROM users').fetchone()['c'] == 1


def test_login_page_loads_when_user_exists(client, app):
    seed_user(app)
    response = client.get('/login')
    assert response.status_code == 200


def test_login_redirects_to_setup_when_no_user(client):
    response = client.get('/login')
    assert response.status_code == 302
    assert response.headers['Location'] == '/setup'


def test_login_success_sets_session(client, app):
    seed_user(app)
    response = client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    assert response.status_code == 302
    assert response.headers['Location'] == '/send/'
    with client.session_transaction() as sess:
        assert 'user_id' in sess


def test_login_wrong_password_fails(client, app):
    seed_user(app)
    response = client.post('/login', data={'username': TEST_USERNAME, 'password': 'wrong'}, follow_redirects=True)
    assert b'Invalid username or password' in response.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_unknown_username_fails(client, app):
    seed_user(app)
    known_user_response = client.post(
        '/login', data={'username': TEST_USERNAME, 'password': 'wrong'}, follow_redirects=True)
    unknown_user_response = client.post(
        '/login', data={'username': 'nobody', 'password': 'wrong'}, follow_redirects=True)
    assert known_user_response.data == unknown_user_response.data


def test_login_clears_pre_existing_session_keys(client, app):
    seed_user(app)
    with client.session_transaction() as sess:
        sess['junk'] = 'leftover'
    client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    with client.session_transaction() as sess:
        assert 'junk' not in sess


def test_login_sets_permanent_session(client, app):
    seed_user(app)
    client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_setup_sets_permanent_session(client):
    client.post('/setup', data={
        'username': 'alice',
        'password': 'a-very-long-password',
        'confirm_password': 'a-very-long-password',
    })
    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_lockout_after_max_failed_attempts(client, app):
    seed_user(app)
    for _ in range(5):
        client.post('/login', data={'username': TEST_USERNAME, 'password': 'wrong'})
    with app.app_context():
        row = get_db().execute('SELECT failed_attempts, locked_until FROM users WHERE username = ?',
                                (TEST_USERNAME,)).fetchone()
        assert row['failed_attempts'] == 5
        assert row['locked_until'] is not None


def test_locked_account_rejects_correct_password(client, app):
    seed_user(app)
    for _ in range(5):
        client.post('/login', data={'username': TEST_USERNAME, 'password': 'wrong'})
    response = client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_lockout_response_matches_unknown_username_response(client, app):
    seed_user(app)
    for _ in range(5):
        # follow_redirects so each attempt's flash is consumed immediately,
        # keeping flash state comparable between the two final requests below.
        client.post('/login', data={'username': TEST_USERNAME, 'password': 'wrong'}, follow_redirects=True)
    locked_response = client.post(
        '/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD}, follow_redirects=True)
    unknown_response = client.post(
        '/login', data={'username': 'nobody', 'password': 'wrong'}, follow_redirects=True)
    # Compare only the flash message, not the full body — the CSRF token
    # embedded in the form is random per render and would never match.
    assert b'Too many' not in locked_response.data
    assert GENERIC_LOGIN_ERROR.encode() in locked_response.data
    assert GENERIC_LOGIN_ERROR.encode() in unknown_response.data


def test_lockout_expires_after_locked_until(client, app):
    seed_user(app)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with app.app_context():
        db = get_db()
        db.execute('UPDATE users SET failed_attempts = 5, locked_until = ? WHERE username = ?',
                   (past, TEST_USERNAME))
        db.commit()
    response = client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    assert response.status_code == 302
    assert response.headers['Location'] == '/send/'


def test_successful_login_resets_failed_attempts(client, app):
    seed_user(app)
    client.post('/login', data={'username': TEST_USERNAME, 'password': 'wrong'})
    client.post('/login', data={'username': TEST_USERNAME, 'password': TEST_PASSWORD})
    with app.app_context():
        row = get_db().execute('SELECT failed_attempts, locked_until FROM users WHERE username = ?',
                                (TEST_USERNAME,)).fetchone()
        assert row['failed_attempts'] == 0
        assert row['locked_until'] is None


def test_logout_clears_session(auth_client):
    response = auth_client.post('/logout')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'
    with auth_client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_logout_get_not_allowed(auth_client):
    response = auth_client.get('/logout')
    assert response.status_code == 405


def test_no_redirect_loop_after_logout(auth_client):
    response = auth_client.post('/logout', follow_redirects=True)
    assert response.status_code == 200


def test_root_redirects_to_setup_when_no_user(client):
    response = client.get('/')
    assert response.status_code == 302
    assert response.headers['Location'] == '/setup'


def test_gated_route_redirects_to_login_when_user_exists(client, app):
    seed_user(app)
    response = client.get('/send/')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'


def test_static_assets_not_gated(client):
    response = client.get('/static/app.css')
    assert response.status_code == 200


def test_unknown_url_does_not_500(client):
    response = client.get('/no-such-page')
    assert response.status_code == 404


def test_authenticated_user_reaches_gated_routes(auth_client):
    response = auth_client.get('/send/')
    assert response.status_code == 200


def test_missing_csrf_token_on_setup_redirects_to_setup(csrf_client):
    response = csrf_client.post('/setup', data={
        'username': 'alice', 'password': 'a-very-long-password', 'confirm_password': 'a-very-long-password',
    })
    assert response.status_code == 302
    assert response.headers['Location'] == '/setup'


def test_change_password_requires_login_get(client, app):
    seed_user(app)
    response = client.get('/change-password')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'


def test_change_password_requires_login_post(client, app):
    seed_user(app)
    response = client.post('/change-password', data={})
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'


def test_change_password_redirects_to_setup_when_no_user(client):
    response = client.get('/change-password')
    assert response.status_code == 302
    assert response.headers['Location'] == '/setup'


def test_change_password_page_loads(auth_client):
    response = auth_client.get('/change-password')
    assert response.status_code == 200


def test_change_password_success(auth_client, app):
    response = auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': 'a-brand-new-password',
        'confirm_password': 'a-brand-new-password',
    })
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute('SELECT password_hash FROM users WHERE username = ?', (TEST_USERNAME,)).fetchone()
    from werkzeug.security import check_password_hash
    assert check_password_hash(row['password_hash'], 'a-brand-new-password')
    assert not check_password_hash(row['password_hash'], TEST_PASSWORD)


def test_change_password_wrong_current_rejected(auth_client, app):
    auth_client.post('/change-password', data={
        'current_password': 'not-the-current-password',
        'new_password': 'a-brand-new-password',
        'confirm_password': 'a-brand-new-password',
    })
    with app.app_context():
        row = get_db().execute('SELECT password_hash FROM users WHERE username = ?', (TEST_USERNAME,)).fetchone()
    from werkzeug.security import check_password_hash
    assert check_password_hash(row['password_hash'], TEST_PASSWORD)


def test_change_password_mismatch_rejected(auth_client):
    response = auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': 'a-brand-new-password',
        'confirm_password': 'a-different-password',
    }, follow_redirects=True)
    assert b'do not match' in response.data


def test_change_password_too_short_rejected(auth_client):
    response = auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': 'short',
        'confirm_password': 'short',
    }, follow_redirects=True)
    assert b'at least' in response.data


def test_change_password_same_as_current_rejected(auth_client):
    response = auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': TEST_PASSWORD,
        'confirm_password': TEST_PASSWORD,
    }, follow_redirects=True)
    assert b'different from your current password' in response.data


def test_change_password_rotates_session(auth_client):
    with auth_client.session_transaction() as sess:
        sess['junk'] = 'leftover'
    auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': 'a-brand-new-password',
        'confirm_password': 'a-brand-new-password',
    })
    with auth_client.session_transaction() as sess:
        assert 'junk' not in sess
        assert 'user_id' in sess


def test_change_password_sets_permanent_session(auth_client):
    auth_client.post('/change-password', data={
        'current_password': TEST_PASSWORD,
        'new_password': 'a-brand-new-password',
        'confirm_password': 'a-brand-new-password',
    })
    with auth_client.session_transaction() as sess:
        assert sess.permanent is True


def test_missing_csrf_token_on_login_redirects_to_login(csrf_client):
    seed_user(csrf_client.application)
    response = csrf_client.post('/login', data={'username': 'alice', 'password': 'whatever'})
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

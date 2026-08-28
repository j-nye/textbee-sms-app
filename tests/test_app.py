import os


def test_samesite_is_lax(app):
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'


def test_httponly_enabled(app):
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True


def test_secure_cookie_defaults_off(app):
    assert app.config['SESSION_COOKIE_SECURE'] is False


def test_secure_cookie_env_driven(tmp_path, monkeypatch):
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'true')
    from web_app.app import create_app
    app = create_app({
        'TESTING': True,
        'DATABASE': str(tmp_path / 'db.sqlite'),
        'SECRET_KEY': 'test-secret',
        'ENV_FILE': None,
        'WTF_CSRF_ENABLED': False,
    })
    assert app.config['SESSION_COOKIE_SECURE'] is True


def test_permanent_session_lifetime_is_30_days(app):
    assert app.config['PERMANENT_SESSION_LIFETIME'].days == 30

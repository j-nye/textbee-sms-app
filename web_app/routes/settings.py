import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('settings', __name__, url_prefix='/settings')


def _read_env(env_file):
    values = {'TEXTBEE_API_KEY': '', 'TEXTBEE_DEVICE_ID': '', 'GOOGLE_CLIENT_SECRET_FILE': '', 'APP_BASE_URL': ''}
    if env_file and os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    values[k.strip()] = v.strip().strip('"\'')
    return values


def _write_env(env_file, key, value):
    """Set or add a key in the .env file."""
    if not env_file:
        return
    if '\n' in value or '\r' in value:
        raise ValueError(f'{key} cannot contain newlines.')
    lines = []
    found = False
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith(f'{key}='):
            new_lines.append(f'{key}={value}\n')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'{key}={value}\n')
    with open(env_file, 'w') as f:
        f.writelines(new_lines)
    os.chmod(env_file, 0o600)


def _google_redirect_uri(env):
    """Build the Google OAuth redirect URI from the operator-configured APP_BASE_URL.

    Never derived from the request Host header (see flask-url-for-external-true).
    Returns None if APP_BASE_URL isn't configured.
    """
    base_url = env.get('APP_BASE_URL', '').strip().rstrip('/')
    if not base_url:
        return None
    # nosemgrep: python.flask.security.audit.flask-url-for-external-true.flask-url-for-external-true -- fixed: built from an operator-configured APP_BASE_URL, not url_for(_external=True)'s request-Host-header-derived URL.
    return base_url + url_for('settings.google_callback')


@bp.route('/', methods=['GET', 'POST'])
def index():
    env_file = current_app.config.get('ENV_FILE')
    env = _read_env(env_file)

    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        device_id = request.form.get('device_id', '').strip()
        google_file = request.form.get('google_client_secret_file', '').strip()
        base_url = request.form.get('app_base_url', '').strip()
        try:
            _write_env(env_file, 'TEXTBEE_API_KEY', api_key)
            _write_env(env_file, 'TEXTBEE_DEVICE_ID', device_id)
            _write_env(env_file, 'GOOGLE_CLIENT_SECRET_FILE', google_file)
            _write_env(env_file, 'APP_BASE_URL', base_url)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('settings.index'))
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    from ..google_sync import TOKEN_FILE
    google_connected = os.path.exists(TOKEN_FILE)
    return render_template('settings.html', env=env, google_connected=google_connected)


@bp.route('/test-connection')
def test_connection():
    env_file = current_app.config.get('ENV_FILE')
    env = _read_env(env_file)
    api_key = env.get('TEXTBEE_API_KEY', '')
    device_id = env.get('TEXTBEE_DEVICE_ID', '')

    if not api_key or not device_id:
        flash('API Key and Device ID are required.', 'error')
        return redirect(url_for('settings.index'))

    import urllib.request, urllib.error, json
    url = f"https://api.textbee.dev/api/v1/gateway/devices/{device_id}/send-sms"
    headers = {'x-api-key': api_key, 'Content-Type': 'application/json'}
    payload = json.dumps({'recipients': [], 'message': 'ping'}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- false positive: url is built from a fixed https://api.textbee.dev host template; only device_id (a path segment) is interpolated, so the scheme/host can't be attacker-controlled.
        urllib.request.urlopen(req)
        flash('Connection successful!', 'success')
    except urllib.error.HTTPError as e:
        if e.code in (400, 422):
            flash('Connection successful! (credentials accepted)', 'success')
        else:
            flash(f'Connection failed: HTTP {e.code}', 'error')
    except urllib.error.URLError as e:
        flash(f'Connection failed: {e.reason}', 'error')

    return redirect(url_for('settings.index'))


@bp.route('/google/connect')
def google_connect():
    from ..google_sync import start_oauth_flow
    from flask import session
    env_file = current_app.config.get('ENV_FILE')
    env = _read_env(env_file)
    client_secret_file = env.get('GOOGLE_CLIENT_SECRET_FILE', '')

    if not client_secret_file or not os.path.exists(client_secret_file):
        flash('Set GOOGLE_CLIENT_SECRET_FILE in Settings to the path of your Google OAuth credentials JSON.', 'error')
        return redirect(url_for('settings.index'))

    redirect_uri = _google_redirect_uri(env)
    if not redirect_uri:
        flash('Set Public Base URL in Settings before connecting Google (used to build the OAuth redirect link).', 'error')
        return redirect(url_for('settings.index'))

    auth_url, state, flow = start_oauth_flow(client_secret_file, redirect_uri)
    session['google_oauth_state'] = state
    session['google_client_secret_file'] = client_secret_file
    return redirect(auth_url)


@bp.route('/google/callback')
def google_callback():
    from ..google_sync import SCOPES, TOKEN_FILE
    from google_auth_oauthlib.flow import InstalledAppFlow
    from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
    from flask import session, request as freq

    client_secret_file = session.get('google_client_secret_file', '')
    expected_state = session.pop('google_oauth_state', None)
    if not client_secret_file or not expected_state:
        flash('OAuth session expired. Please try again.', 'error')
        return redirect(url_for('settings.index'))

    env_file = current_app.config.get('ENV_FILE')
    env = _read_env(env_file)
    redirect_uri = _google_redirect_uri(env)
    if not redirect_uri:
        flash('OAuth session expired. Please try again.', 'error')
        return redirect(url_for('settings.index'))

    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file, SCOPES, redirect_uri=redirect_uri, state=expected_state
    )
    try:
        flow.fetch_token(authorization_response=freq.url)
    except MismatchingStateError:
        flash('OAuth state mismatch. Please try connecting again.', 'error')
        return redirect(url_for('settings.index'))
    except Exception:
        flash('Google OAuth callback failed. Please try again.', 'error')
        return redirect(url_for('settings.index'))
    creds = flow.credentials

    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)

    flash('Google account connected successfully!', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/google/disconnect', methods=['POST'])
def google_disconnect():
    from ..google_sync import disconnect
    disconnect()
    flash('Google account disconnected.', 'success')
    return redirect(url_for('settings.index'))

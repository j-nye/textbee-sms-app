import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('settings', __name__, url_prefix='/settings')


def _read_env(env_file):
    values = {'TEXTBEE_API_KEY': '', 'TEXTBEE_DEVICE_ID': '', 'GOOGLE_CLIENT_SECRET_FILE': ''}
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


@bp.route('/', methods=['GET', 'POST'])
def index():
    env_file = current_app.config.get('ENV_FILE')
    env = _read_env(env_file)

    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        device_id = request.form.get('device_id', '').strip()
        google_file = request.form.get('google_client_secret_file', '').strip()
        _write_env(env_file, 'TEXTBEE_API_KEY', api_key)
        _write_env(env_file, 'TEXTBEE_DEVICE_ID', device_id)
        _write_env(env_file, 'GOOGLE_CLIENT_SECRET_FILE', google_file)
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    token_path = os.path.join(os.path.dirname(current_app.root_path), 'token.json')
    google_connected = os.path.exists(token_path)
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

    redirect_uri = url_for('settings.google_callback', _external=True)
    auth_url, state, flow = start_oauth_flow(client_secret_file, redirect_uri)
    session['google_oauth_state'] = state
    session['google_client_secret_file'] = client_secret_file
    return redirect(auth_url)


@bp.route('/google/callback')
def google_callback():
    from ..google_sync import SCOPES, TOKEN_FILE
    from google_auth_oauthlib.flow import InstalledAppFlow
    from flask import session, request as freq

    client_secret_file = session.get('google_client_secret_file', '')
    if not client_secret_file:
        flash('OAuth session expired. Please try again.', 'error')
        return redirect(url_for('settings.index'))

    redirect_uri = url_for('settings.google_callback', _external=True)
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES, redirect_uri=redirect_uri)
    flow.fetch_token(authorization_response=freq.url)
    creds = flow.credentials

    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())

    flash('Google account connected successfully!', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/google/disconnect')
def google_disconnect():
    from ..google_sync import disconnect
    disconnect()
    flash('Google account disconnected.', 'success')
    return redirect(url_for('settings.index'))

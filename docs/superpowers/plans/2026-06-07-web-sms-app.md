# Web SMS App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Flask web app for sending SMS via Textbee, with contact management, message history, markdown templates, and Google Contacts sync — sharing the existing `contacts.db` with `sms.py`.

**Architecture:** Flask app with Blueprint-per-page routing, a shared `db.py` for SQLite access, and isolated modules for Textbee and Google Contacts logic. The existing CLI app (`sms.py`) is untouched — both apps read/write the same `contacts.db`.

**Tech Stack:** Python 3, Flask 3, SQLite (via stdlib `sqlite3`), mistune 3 (markdown), google-auth-oauthlib, google-api-python-client, python-dotenv, pytest

> **IMPORTANT — Documentation:** Before implementing any step that uses a library, fetch current docs via Context7 MCP:
> 1. `resolve-library-id` with the library name
> 2. `query-docs` with the library ID and your specific question
>
> Do this for: Flask, mistune, google-auth-oauthlib, google-api-python-client, python-dotenv. Never rely on training-data knowledge for these.

---

## File Map

```
SMS-App/
├── sms.py                        # UNTOUCHED
├── contacts.db                   # shared, untouched schema
├── requirements.txt              # CREATE — pip dependencies
├── web_app/
│   ├── __init__.py               # CREATE — empty, marks as package
│   ├── app.py                    # CREATE — Flask app factory + blueprint registration
│   ├── db.py                     # CREATE — DB init (new tables), get_db() helper
│   ├── textbee.py                # CREATE — send_sms() extracted/adapted from sms.py
│   ├── google_sync.py            # CREATE — Google People API OAuth + sync logic
│   ├── routes/
│   │   ├── __init__.py           # CREATE — empty
│   │   ├── help.py               # CREATE — /help route
│   │   ├── settings.py           # CREATE — /settings GET/POST + OAuth callback
│   │   ├── contacts.py           # CREATE — /contacts CRUD + CSV import + Google sync trigger
│   │   ├── msg_templates.py      # CREATE — /templates CRUD (named msg_templates to avoid stdlib conflict)
│   │   ├── send.py               # CREATE — /send GET/POST
│   │   └── history.py            # CREATE — /history GET
│   ├── templates/                # Jinja2 HTML files
│   │   ├── base.html             # CREATE — sidebar shell, nav, flash messages
│   │   ├── help.html             # CREATE
│   │   ├── settings.html         # CREATE
│   │   ├── contacts.html         # CREATE
│   │   ├── msg_templates.html    # CREATE
│   │   ├── send.html             # CREATE
│   │   └── history.html          # CREATE
│   └── static/
│       └── app.css               # CREATE — minimal sidebar layout styles
└── tests/
    ├── conftest.py               # CREATE — Flask test client, in-memory DB fixture
    ├── test_db.py                # CREATE
    ├── test_textbee.py           # CREATE
    ├── test_google_sync.py       # CREATE
    └── routes/
        ├── test_help.py          # CREATE
        ├── test_settings.py      # CREATE
        ├── test_contacts.py      # CREATE
        ├── test_msg_templates.py # CREATE
        ├── test_send.py          # CREATE
        └── test_history.py       # CREATE
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `web_app/__init__.py`
- Create: `web_app/routes/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/routes/` (directory)

- [ ] **Step 1: Create requirements.txt**

```
Flask>=3.0
google-auth-oauthlib>=1.2
google-api-python-client>=2.100
mistune>=3.0
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 3: Create package init files**

Create `web_app/__init__.py` — empty file.
Create `web_app/routes/__init__.py` — empty file.
Create `tests/__init__.py` — empty file.
Create `tests/routes/__init__.py` — empty file.

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from web_app.app import create_app
from web_app.db import init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret',
        'ENV_FILE': None,
    })
    with app.app_context():
        init_db()
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt web_app/__init__.py web_app/routes/__init__.py tests/
git commit -m "feat: project setup — requirements, package structure, test fixtures"
```

---

## Task 2: Database Layer

**Files:**
- Create: `web_app/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```

Expected: ImportError or ModuleNotFoundError (web_app.db doesn't exist yet).

- [ ] **Step 3: Fetch Flask docs via Context7**

Use Context7 MCP:
- `resolve-library-id` → search "Flask"
- `query-docs` → "Flask application context g object sqlite3 database connection"

- [ ] **Step 4: Create web_app/db.py**

```python
import sqlite3
import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            group_name TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipients TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at DATETIME NOT NULL,
            status TEXT NOT NULL,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS msg_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            body_markdown TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
    ''')
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
```

- [ ] **Step 5: Create web_app/app.py (minimal, enough for tests)**

```python
import os
from flask import Flask
from . import db as database


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)

    app.config.from_mapping(
        SECRET_KEY='dev-change-in-production',
        DATABASE=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'contacts.db'),
        ENV_FILE=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
    )

    if test_config is not None:
        app.config.update(test_config)

    database.init_app(app)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        database.init_db()
    app.run(debug=True, port=5000)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web_app/db.py web_app/app.py tests/test_db.py
git commit -m "feat: database layer — init_db, get_db, messages and msg_templates tables"
```

---

## Task 3: Base Layout + Static Assets

**Files:**
- Create: `web_app/templates/base.html`
- Create: `web_app/static/app.css`

- [ ] **Step 1: Create web_app/static/app.css**

```css
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    background: #f8fafc;
    color: #1e293b;
    display: flex;
    height: 100vh;
    overflow: hidden;
}

/* Sidebar */
#sidebar {
    width: 200px;
    background: #1e293b;
    color: #cbd5e1;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    padding: 0;
}

#sidebar .brand {
    padding: 20px 16px 16px;
    font-weight: 700;
    font-size: 15px;
    color: #fff;
    border-bottom: 1px solid #334155;
}

#sidebar nav a {
    display: block;
    padding: 10px 16px;
    color: #94a3b8;
    text-decoration: none;
    border-left: 3px solid transparent;
    transition: background 0.15s;
}

#sidebar nav a:hover {
    background: #334155;
    color: #fff;
}

#sidebar nav a.active {
    background: #334155;
    color: #fff;
    border-left-color: #3b82f6;
}

/* Main content */
#content {
    flex: 1;
    overflow-y: auto;
    padding: 28px 32px;
}

h1 { font-size: 20px; font-weight: 700; margin-bottom: 20px; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; }

/* Flash messages */
.flash { padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
.flash.success { background: #dcfce7; color: #166534; }
.flash.error   { background: #fee2e2; color: #991b1b; }
.flash.info    { background: #dbeafe; color: #1e40af; }

/* Forms */
label { display: block; font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; margin-top: 12px; }
input[type=text], input[type=password], textarea, select {
    width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1;
    border-radius: 6px; font-size: 14px; background: #fff;
}
textarea { resize: vertical; }

/* Buttons */
.btn { display: inline-block; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; text-decoration: none; }
.btn-primary   { background: #3b82f6; color: #fff; }
.btn-danger    { background: #ef4444; color: #fff; }
.btn-secondary { background: #e2e8f0; color: #1e293b; }
.btn-sm        { padding: 5px 10px; font-size: 12px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 12px; background: #f1f5f9; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; }
td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
tr:last-child td { border-bottom: none; }

/* Cards */
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

/* Markdown preview */
.md-preview { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; min-height: 80px; font-size: 13px; line-height: 1.6; }
.md-preview p { margin-bottom: 8px; }
.md-preview ul, .md-preview ol { margin-left: 20px; margin-bottom: 8px; }
```

- [ ] **Step 2: Fetch Flask Jinja2 docs via Context7**

Use Context7 MCP:
- `resolve-library-id` → search "Flask"
- `query-docs` → "Jinja2 template inheritance block extends base template url_for get_flashed_messages"

- [ ] **Step 3: Create web_app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}SMS App{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
</head>
<body>
    <div id="sidebar">
        <div class="brand">📱 SMS App</div>
        <nav>
            <a href="{{ url_for('send.index') }}"         class="{{ 'active' if request.endpoint == 'send.index' }}">✉️ Send</a>
            <a href="{{ url_for('contacts.index') }}"     class="{{ 'active' if request.endpoint and request.endpoint.startswith('contacts.') }}">👥 Contacts</a>
            <a href="{{ url_for('msg_templates.index') }}" class="{{ 'active' if request.endpoint and request.endpoint.startswith('msg_templates.') }}">📋 Templates</a>
            <a href="{{ url_for('history.index') }}"      class="{{ 'active' if request.endpoint == 'history.index' }}">🕐 History</a>
            <a href="{{ url_for('settings.index') }}"     class="{{ 'active' if request.endpoint == 'settings.index' }}">⚙️ Settings</a>
            <a href="{{ url_for('help.index') }}"         class="{{ 'active' if request.endpoint == 'help.index' }}">❓ Help</a>
        </nav>
    </div>
    <div id="content">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% for category, message in messages %}
            <div class="flash {{ category }}">{{ message }}</div>
          {% endfor %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

- [ ] **Step 4: Commit**

```bash
git add web_app/static/app.css web_app/templates/base.html
git commit -m "feat: base layout — sidebar nav, CSS, flash messages"
```

---

## Task 4: Textbee Module

**Files:**
- Create: `web_app/textbee.py`
- Create: `tests/test_textbee.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_textbee.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from web_app.textbee import send_sms, normalize_phone


def test_normalize_phone_10_digits():
    assert normalize_phone('5551234567') == '+15551234567'


def test_normalize_phone_11_digits_leading_1():
    assert normalize_phone('15551234567') == '+15551234567'


def test_normalize_phone_already_e164():
    assert normalize_phone('+15551234567') == '+15551234567'


def test_normalize_phone_with_dashes():
    assert normalize_phone('555-123-4567') == '+15551234567'


def test_normalize_phone_with_parens():
    assert normalize_phone('(555) 123-4567') == '+15551234567'


def test_send_sms_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({'success': True}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response):
        result = send_sms('api-key', 'device-id', ['+15551234567'], 'Hello!')

    assert result['success'] is True
    assert result['error'] is None


def test_send_sms_network_failure():
    import urllib.error
    with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('timeout')):
        result = send_sms('api-key', 'device-id', ['+15551234567'], 'Hello!')

    assert result['success'] is False
    assert 'timeout' in result['error']
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_textbee.py -v
```

Expected: ImportError (web_app.textbee doesn't exist yet).

- [ ] **Step 3: Create web_app/textbee.py**

```python
import json
import re
import urllib.request
import urllib.error

TEXTBEE_URL = "https://api.textbee.dev/api/v1/gateway/devices/{device_id}/send-sms"


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format (+1XXXXXXXXXX for US numbers)."""
    phone_str = phone.strip()
    has_plus = phone_str.startswith('+')
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return phone_str
    if has_plus:
        return '+' + digits
    if len(digits) == 10:
        return '+1' + digits
    if len(digits) == 11 and digits.startswith('1'):
        return '+' + digits
    return digits


def send_sms(api_key: str, device_id: str, recipients: list[str], message: str) -> dict:
    """
    Send an SMS via Textbee API.

    Returns:
        dict with keys:
            success (bool)
            error (str or None)
    """
    url = TEXTBEE_URL.format(device_id=device_id)
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'SMS-WebApp/1.0',
    }
    payload = json.dumps({'recipients': recipients, 'message': message}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'error': None, 'data': result}
    except urllib.error.URLError as e:
        error_msg = str(e.reason) if hasattr(e, 'reason') else str(e)
        return {'success': False, 'error': error_msg}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_textbee.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app/textbee.py tests/test_textbee.py
git commit -m "feat: textbee module — send_sms and normalize_phone"
```

---

## Task 5: Help Page

**Files:**
- Create: `web_app/routes/help.py`
- Create: `web_app/templates/help.html`
- Modify: `web_app/app.py`
- Create: `tests/routes/test_help.py`

This task validates the full Flask stack end-to-end before building feature pages.

- [ ] **Step 1: Write failing test**

Create `tests/routes/test_help.py`:

```python
def test_help_page_returns_200(client):
    response = client.get('/help')
    assert response.status_code == 200


def test_help_page_contains_getting_started(client):
    response = client.get('/help')
    assert b'Getting Started' in response.data


def test_help_page_contains_all_sections(client):
    response = client.get('/help')
    for section in [b'Send a Message', b'Contacts', b'Templates', b'History', b'Settings', b'CLI App']:
        assert section in response.data, f"Missing section: {section}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/routes/test_help.py -v
```

Expected: FAIL — no route registered for /help.

- [ ] **Step 3: Create web_app/routes/help.py**

```python
from flask import Blueprint, render_template

bp = Blueprint('help', __name__, url_prefix='/help')


@bp.route('/')
def index():
    return render_template('help.html')
```

- [ ] **Step 4: Create web_app/templates/help.html**

```html
{% extends "base.html" %}
{% block title %}Help — SMS App{% endblock %}
{% block content %}
<h1>Help</h1>

<div class="card">
  <h2>Getting Started</h2>
  <p>Prerequisites:</p>
  <ol style="margin-left:20px;margin-top:8px;line-height:1.8">
    <li>Create a free account at <strong>textbee.dev</strong></li>
    <li>Install the Textbee Android app on your phone and link it to your account</li>
    <li>Copy your <strong>API Key</strong> and <strong>Device ID</strong> from the Textbee dashboard</li>
    <li>Enter them in <a href="{{ url_for('settings.index') }}">Settings</a></li>
  </ol>
  <p style="margin-top:12px">Run the app: <code>python web_app/app.py</code> then open <strong>http://localhost:5000</strong></p>
</div>

<div class="card">
  <h2>Send a Message</h2>
  <ol style="margin-left:20px;line-height:1.8">
    <li>Go to <a href="{{ url_for('send.index') }}">Send</a></li>
    <li>Choose a recipient — search by name, pick a group, or type a number</li>
    <li>Type your message or select a saved <a href="{{ url_for('msg_templates.index') }}">Template</a></li>
    <li>Click <strong>Send SMS</strong></li>
  </ol>
</div>

<div class="card">
  <h2>Contacts</h2>
  <ul style="margin-left:20px;line-height:1.8">
    <li><strong>Add:</strong> Click "Add Contact", fill in name and phone number, optionally a group</li>
    <li><strong>Edit/Delete:</strong> Use the buttons in the contacts table</li>
    <li><strong>Import CSV:</strong> Your CSV must have <code>Name</code> and <code>Phone</code> columns; <code>Group</code> is optional</li>
    <li><strong>Google Sync:</strong> Click "Sync Google Contacts" — you'll be asked to sign in the first time. Contacts are merged by phone number.</li>
  </ul>
  <p style="margin-top:10px"><strong>Google OAuth setup:</strong> You need a Google Cloud project with the People API enabled and an OAuth 2.0 client ID (Desktop app type). Download the credentials JSON and set <code>GOOGLE_CLIENT_SECRET_FILE</code> in Settings.</p>
</div>

<div class="card">
  <h2>Templates</h2>
  <ul style="margin-left:20px;line-height:1.8">
    <li>Go to <a href="{{ url_for('msg_templates.index') }}">Templates</a> and click "New Template"</li>
    <li>Write your message using <strong>Markdown</strong> — a live preview is shown alongside the editor</li>
    <li>Templates are selected on the Send page and rendered to plain text before sending</li>
  </ul>
  <p style="margin-top:10px"><strong>Markdown quick reference:</strong> <code>**bold**</code>, <code>*italic*</code>, <code>- list item</code>, blank line = new paragraph</p>
</div>

<div class="card">
  <h2>History</h2>
  <p>Every sent message is logged in <a href="{{ url_for('history.index') }}">History</a> with:</p>
  <ul style="margin-left:20px;margin-top:8px;line-height:1.8">
    <li><strong>sent</strong> — message delivered to the Textbee API queue successfully</li>
    <li><strong>failed</strong> — an error occurred; click the row to see the error detail</li>
  </ul>
  <p style="margin-top:8px">Note: "sent" means Textbee accepted the request — delivery to the recipient depends on your phone being online.</p>
</div>

<div class="card">
  <h2>Settings</h2>
  <ul style="margin-left:20px;line-height:1.8">
    <li><strong>API Key / Device ID:</strong> Found in your Textbee dashboard under "Devices"</li>
    <li><strong>Test Connection:</strong> Sends a ping to the Textbee API to verify credentials</li>
    <li><strong>Google Account:</strong> Connect to enable Google Contacts sync; Disconnect removes the stored token</li>
  </ul>
</div>

<div class="card">
  <h2>CLI App</h2>
  <p>The original <code>sms.py</code> command-line app continues to work independently. Both apps share the same <code>contacts.db</code> database, so contacts added in either app are visible in both.</p>
  <p style="margin-top:8px">Run it with: <code>python sms.py</code></p>
</div>
{% endblock %}
```

- [ ] **Step 5: Register blueprint in web_app/app.py**

Update `web_app/app.py` — replace the `return app` line with blueprint registration:

```python
import os
from flask import Flask
from . import db as database


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)

    app.config.from_mapping(
        SECRET_KEY='dev-change-in-production',
        DATABASE=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'contacts.db'),
        ENV_FILE=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
    )

    if test_config is not None:
        app.config.update(test_config)

    database.init_app(app)

    from .routes import help, send, contacts, msg_templates, history, settings
    app.register_blueprint(help.bp)
    app.register_blueprint(send.bp)
    app.register_blueprint(contacts.bp)
    app.register_blueprint(msg_templates.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(settings.bp)

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('send.index'))

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        database.init_db()
    app.run(debug=True, port=5000)
```

Note: The other blueprints don't exist yet — create stub files so the import doesn't fail. For each of `send.py`, `contacts.py`, `msg_templates.py`, `history.py`, `settings.py`, create a minimal stub:

`web_app/routes/send.py`:
```python
from flask import Blueprint, render_template
bp = Blueprint('send', __name__, url_prefix='/send')

@bp.route('/')
def index():
    return render_template('send.html')
```

`web_app/routes/contacts.py`:
```python
from flask import Blueprint, render_template
bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@bp.route('/')
def index():
    return render_template('contacts.html')
```

`web_app/routes/msg_templates.py`:
```python
from flask import Blueprint, render_template
bp = Blueprint('msg_templates', __name__, url_prefix='/templates')

@bp.route('/')
def index():
    return render_template('msg_templates.html')
```

`web_app/routes/history.py`:
```python
from flask import Blueprint, render_template
bp = Blueprint('history', __name__, url_prefix='/history')

@bp.route('/')
def index():
    return render_template('history.html')
```

`web_app/routes/settings.py`:
```python
from flask import Blueprint, render_template
bp = Blueprint('settings', __name__, url_prefix='/settings')

@bp.route('/')
def index():
    return render_template('settings.html')
```

Create minimal stub Jinja2 templates for each stub route (`send.html`, `contacts.html`, `msg_templates.html`, `history.html`, `settings.html`):

Each file:
```html
{% extends "base.html" %}
{% block content %}<h1>Coming soon</h1>{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/routes/test_help.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Smoke test in browser**

```bash
python web_app/app.py
```

Open http://localhost:5000/help — verify sidebar renders, Help page content is visible.
Stop server with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add web_app/routes/ web_app/templates/ web_app/app.py tests/routes/test_help.py
git commit -m "feat: help page + blueprint stubs — full Flask stack validated"
```

---

## Task 6: Settings Page

**Files:**
- Modify: `web_app/routes/settings.py`
- Modify: `web_app/templates/settings.html`
- Create: `tests/routes/test_settings.py`

- [ ] **Step 1: Fetch python-dotenv docs via Context7**

Use Context7 MCP:
- `resolve-library-id` → search "python-dotenv"
- `query-docs` → "set_key dotenv_values read write .env file"

- [ ] **Step 2: Write failing tests**

Create `tests/routes/test_settings.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/routes/test_settings.py -v
```

Expected: FAIL — stub settings route doesn't handle POST or read .env.

- [ ] **Step 4: Update web_app/routes/settings.py**

```python
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('settings', __name__, url_prefix='/settings')


def _read_env(env_file):
    values = {'TEXTBEE_API_KEY': '', 'TEXTBEE_DEVICE_ID': ''}
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
        _write_env(env_file, 'TEXTBEE_API_KEY', api_key)
        _write_env(env_file, 'TEXTBEE_DEVICE_ID', device_id)
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    google_connected = os.path.exists(
        os.path.join(os.path.dirname(current_app.root_path), 'token.json')
    )
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

    from ..textbee import send_sms
    # Textbee has no dedicated ping endpoint; we attempt a send with an empty recipients
    # list which returns an error but confirms the API key is accepted.
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
```

- [ ] **Step 5: Update web_app/templates/settings.html**

```html
{% extends "base.html" %}
{% block title %}Settings — SMS App{% endblock %}
{% block content %}
<h1>Settings</h1>

<div class="card">
  <h2>Textbee Credentials</h2>
  <p style="color:#64748b;font-size:13px;margin-bottom:12px">Find these in your <a href="https://textbee.dev" target="_blank">Textbee dashboard</a> under Devices.</p>
  <form method="post">
    <label>API Key</label>
    <input type="text" name="api_key" value="{{ env.get('TEXTBEE_API_KEY', '') }}">
    <label>Device ID</label>
    <input type="text" name="device_id" value="{{ env.get('TEXTBEE_DEVICE_ID', '') }}">
    <div style="margin-top:16px;display:flex;gap:10px">
      <button type="submit" class="btn btn-primary">Save</button>
      <a href="{{ url_for('settings.test_connection') }}" class="btn btn-secondary">Test Connection</a>
    </div>
  </form>
</div>

<div class="card">
  <h2>Google Contacts</h2>
  {% if google_connected %}
    <p style="color:#16a34a;margin-bottom:12px">✅ Connected</p>
    <a href="{{ url_for('settings.google_disconnect') }}" class="btn btn-danger btn-sm">Disconnect</a>
  {% else %}
    <p style="color:#64748b;font-size:13px;margin-bottom:12px">Connect your Google account to sync contacts.</p>
    <a href="{{ url_for('settings.google_connect') }}" class="btn btn-primary btn-sm">Connect Google Account</a>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/routes/test_settings.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web_app/routes/settings.py web_app/templates/settings.html tests/routes/test_settings.py
git commit -m "feat: settings page — Textbee credentials read/write, test connection"
```

---

## Task 7: Contacts Page

**Files:**
- Modify: `web_app/routes/contacts.py`
- Modify: `web_app/templates/contacts.html`
- Create: `tests/routes/test_contacts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/routes/test_contacts.py`:

```python
import io


def test_contacts_page_loads(client):
    response = client.get('/contacts/')
    assert response.status_code == 200


def test_add_contact(client):
    response = client.post('/contacts/add', data={
        'name': 'Alice Smith',
        'phone': '5551234567',
        'group_name': 'Friends',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Alice Smith' in response.data


def test_add_contact_normalizes_phone(client):
    client.post('/contacts/add', data={
        'name': 'Bob Jones',
        'phone': '5559876543',
        'group_name': '',
    })
    response = client.get('/contacts/')
    assert b'+15559876543' in response.data


def test_delete_contact(client, app):
    client.post('/contacts/add', data={'name': 'Temp', 'phone': '5550001111', 'group_name': ''})
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        contact_id = db.execute("SELECT id FROM contacts WHERE name='Temp'").fetchone()[0]
    response = client.post(f'/contacts/delete/{contact_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b'Temp' not in response.data


def test_update_contact(client, app):
    client.post('/contacts/add', data={'name': 'Old Name', 'phone': '5550002222', 'group_name': ''})
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        contact_id = db.execute("SELECT id FROM contacts WHERE name='Old Name'").fetchone()[0]
    response = client.post(f'/contacts/edit/{contact_id}', data={
        'name': 'New Name', 'phone': '5550002222', 'group_name': 'Team'
    }, follow_redirects=True)
    assert b'New Name' in response.data


def test_import_csv(client):
    csv_content = b"Name,Phone,Group\nCarol White,5553334444,Work\nDave Black,5555556666,Work\n"
    data = {'file': (io.BytesIO(csv_content), 'contacts.csv')}
    response = client.post('/contacts/import', data=data,
                           content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b'Carol White' in response.data


def test_empty_name_rejected(client):
    response = client.post('/contacts/add', data={
        'name': '', 'phone': '5551234567', 'group_name': ''
    }, follow_redirects=True)
    assert b'Name is required' in response.data


def test_empty_phone_rejected(client):
    response = client.post('/contacts/add', data={
        'name': 'No Phone', 'phone': '', 'group_name': ''
    }, follow_redirects=True)
    assert b'Phone is required' in response.data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/routes/test_contacts.py -v
```

Expected: FAIL — stub contacts route has no POST handlers.

- [ ] **Step 3: Update web_app/routes/contacts.py**

```python
import csv
import io
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..db import get_db
from ..textbee import normalize_phone

bp = Blueprint('contacts', __name__, url_prefix='/contacts')


@bp.route('/')
def index():
    db = get_db()
    contacts = db.execute(
        'SELECT id, name, phone, group_name FROM contacts ORDER BY name'
    ).fetchall()
    groups = db.execute(
        'SELECT DISTINCT group_name FROM contacts WHERE group_name IS NOT NULL AND group_name != "" ORDER BY group_name'
    ).fetchall()
    return render_template('contacts.html', contacts=contacts, groups=[r[0] for r in groups])


@bp.route('/add', methods=['POST'])
def add():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    group_name = request.form.get('group_name', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('contacts.index'))
    if not phone:
        flash('Phone is required.', 'error')
        return redirect(url_for('contacts.index'))

    clean_phone = normalize_phone(phone)
    db = get_db()
    db.execute(
        'INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, ?)',
        (name, clean_phone, group_name or None)
    )
    db.commit()
    flash(f'Contact "{name}" added.', 'success')
    return redirect(url_for('contacts.index'))


@bp.route('/edit/<int:contact_id>', methods=['POST'])
def edit(contact_id):
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    group_name = request.form.get('group_name', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('contacts.index'))
    if not phone:
        flash('Phone is required.', 'error')
        return redirect(url_for('contacts.index'))

    clean_phone = normalize_phone(phone)
    db = get_db()
    db.execute(
        'UPDATE contacts SET name=?, phone=?, group_name=? WHERE id=?',
        (name, clean_phone, group_name or None, contact_id)
    )
    db.commit()
    flash('Contact updated.', 'success')
    return redirect(url_for('contacts.index'))


@bp.route('/delete/<int:contact_id>', methods=['POST'])
def delete(contact_id):
    db = get_db()
    row = db.execute('SELECT name FROM contacts WHERE id=?', (contact_id,)).fetchone()
    if row:
        db.execute('DELETE FROM contacts WHERE id=?', (contact_id,))
        db.commit()
        flash(f'Contact "{row[0]}" deleted.', 'success')
    return redirect(url_for('contacts.index'))


@bp.route('/import', methods=['POST'])
def import_csv():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a .csv file.', 'error')
        return redirect(url_for('contacts.index'))

    stream = io.StringIO(file.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    fieldnames = [f.lower() for f in (reader.fieldnames or [])]

    if 'name' not in fieldnames or 'phone' not in fieldnames:
        flash('CSV must have Name and Phone columns.', 'error')
        return redirect(url_for('contacts.index'))

    db = get_db()
    count = 0
    for row in reader:
        row_lower = {k.lower(): v for k, v in row.items()}
        name = row_lower.get('name', '').strip()
        phone = row_lower.get('phone', '').strip()
        group = row_lower.get('group', '').strip()
        if name and phone:
            db.execute(
                'INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, ?)',
                (name, normalize_phone(phone), group or None)
            )
            count += 1
    db.commit()
    flash(f'Imported {count} contacts.', 'success')
    return redirect(url_for('contacts.index'))
```

- [ ] **Step 4: Update web_app/templates/contacts.html**

```html
{% extends "base.html" %}
{% block title %}Contacts — SMS App{% endblock %}
{% block content %}
<h1>Contacts</h1>

<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
  <button class="btn btn-primary" onclick="document.getElementById('add-form').style.display='block';this.style.display='none'">+ Add Contact</button>
  <button class="btn btn-secondary" onclick="document.getElementById('import-form').style.display='block';this.style.display='none'">Import CSV</button>
  <a href="{{ url_for('contacts.google_sync') }}" class="btn btn-secondary">Sync Google Contacts</a>
</div>

<div id="add-form" class="card" style="display:none">
  <h2>Add Contact</h2>
  <form method="post" action="{{ url_for('contacts.add') }}">
    <label>Name</label><input type="text" name="name" required>
    <label>Phone</label><input type="text" name="phone" required placeholder="+1 or 10 digits">
    <label>Group (optional)</label><input type="text" name="group_name" list="groups">
    <datalist id="groups">{% for g in groups %}<option value="{{ g }}">{% endfor %}</datalist>
    <div style="margin-top:14px;display:flex;gap:8px">
      <button type="submit" class="btn btn-primary">Save</button>
      <button type="button" class="btn btn-secondary" onclick="this.closest('#add-form').style.display='none'">Cancel</button>
    </div>
  </form>
</div>

<div id="import-form" class="card" style="display:none">
  <h2>Import from CSV</h2>
  <p style="font-size:13px;color:#64748b;margin-bottom:10px">CSV must have <code>Name</code> and <code>Phone</code> columns. <code>Group</code> is optional.</p>
  <form method="post" action="{{ url_for('contacts.import_csv') }}" enctype="multipart/form-data">
    <input type="file" name="file" accept=".csv" required>
    <div style="margin-top:14px"><button type="submit" class="btn btn-primary">Import</button></div>
  </form>
</div>

{% if contacts %}
<div class="card" style="padding:0">
  <table>
    <thead><tr><th>Name</th><th>Phone</th><th>Group</th><th></th></tr></thead>
    <tbody>
    {% for c in contacts %}
    <tr>
      <td>{{ c['name'] }}</td>
      <td>{{ c['phone'] }}</td>
      <td>{{ c['group_name'] or '—' }}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-secondary btn-sm" onclick="toggleEdit({{ c['id'] }})">Edit</button>
        <form method="post" action="{{ url_for('contacts.delete', contact_id=c['id']) }}" style="display:inline" onsubmit="return confirm('Delete {{ c['name'] }}?')">
          <button type="submit" class="btn btn-danger btn-sm">Delete</button>
        </form>
      </td>
    </tr>
    <tr id="edit-{{ c['id'] }}" style="display:none;background:#f8fafc">
      <td colspan="4" style="padding:12px">
        <form method="post" action="{{ url_for('contacts.edit', contact_id=c['id']) }}">
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end">
            <div><label>Name</label><input type="text" name="name" value="{{ c['name'] }}" required></div>
            <div><label>Phone</label><input type="text" name="phone" value="{{ c['phone'] }}" required></div>
            <div><label>Group</label><input type="text" name="group_name" value="{{ c['group_name'] or '' }}" list="groups"></div>
            <div style="margin-top:20px;display:flex;gap:6px">
              <button type="submit" class="btn btn-primary btn-sm">Save</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="toggleEdit({{ c['id'] }})">Cancel</button>
            </div>
          </div>
        </form>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<p style="color:#64748b">No contacts yet. Add one above or import a CSV.</p>
{% endif %}

<script>
function toggleEdit(id) {
  const row = document.getElementById('edit-' + id);
  row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
}
</script>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/routes/test_contacts.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web_app/routes/contacts.py web_app/templates/contacts.html tests/routes/test_contacts.py
git commit -m "feat: contacts page — CRUD, CSV import, phone normalization"
```

---

## Task 8: Message Templates Page

**Files:**
- Modify: `web_app/routes/msg_templates.py`
- Modify: `web_app/templates/msg_templates.html`
- Create: `tests/routes/test_msg_templates.py`

- [ ] **Step 1: Fetch mistune docs via Context7**

Use Context7 MCP:
- `resolve-library-id` → search "mistune"
- `query-docs` → "mistune markdown to html create markdown instance"

- [ ] **Step 2: Write failing tests**

Create `tests/routes/test_msg_templates.py`:

```python
def test_templates_page_loads(client):
    response = client.get('/templates/')
    assert response.status_code == 200


def test_create_template(client):
    response = client.post('/templates/create', data={
        'name': 'Game Reminder',
        'body_markdown': '**Reminder:** Game is at 7pm tonight!',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Game Reminder' in response.data


def test_delete_template(client, app):
    client.post('/templates/create', data={
        'name': 'To Delete', 'body_markdown': 'bye'
    })
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        tmpl_id = db.execute("SELECT id FROM msg_templates WHERE name='To Delete'").fetchone()[0]
    response = client.post(f'/templates/delete/{tmpl_id}', follow_redirects=True)
    assert b'To Delete' not in response.data


def test_empty_name_rejected(client):
    response = client.post('/templates/create', data={
        'name': '', 'body_markdown': 'hello'
    }, follow_redirects=True)
    assert b'Name is required' in response.data


def test_template_preview_endpoint(client, app):
    client.post('/templates/create', data={
        'name': 'Bold Test', 'body_markdown': '**hello**'
    })
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        tmpl_id = db.execute("SELECT id FROM msg_templates WHERE name='Bold Test'").fetchone()[0]
    response = client.get(f'/templates/preview/{tmpl_id}')
    assert response.status_code == 200
    assert b'<strong>' in response.data or b'hello' in response.data
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/routes/test_msg_templates.py -v
```

Expected: FAIL — stub route has no POST handlers.

- [ ] **Step 4: Update web_app/routes/msg_templates.py**

```python
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
import mistune
from ..db import get_db

bp = Blueprint('msg_templates', __name__, url_prefix='/templates')
_markdown = mistune.create_markdown()


@bp.route('/')
def index():
    db = get_db()
    templates = db.execute(
        'SELECT id, name, body_markdown, updated_at FROM msg_templates ORDER BY name'
    ).fetchall()
    return render_template('msg_templates.html', templates=templates, markdown=_markdown)


@bp.route('/create', methods=['POST'])
def create():
    name = request.form.get('name', '').strip()
    body = request.form.get('body_markdown', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('msg_templates.index'))

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        'INSERT INTO msg_templates (name, body_markdown, created_at, updated_at) VALUES (?, ?, ?, ?)',
        (name, body, now, now)
    )
    db.commit()
    flash(f'Template "{name}" saved.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/edit/<int:tmpl_id>', methods=['POST'])
def edit(tmpl_id):
    name = request.form.get('name', '').strip()
    body = request.form.get('body_markdown', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('msg_templates.index'))

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        'UPDATE msg_templates SET name=?, body_markdown=?, updated_at=? WHERE id=?',
        (name, body, now, tmpl_id)
    )
    db.commit()
    flash('Template updated.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/delete/<int:tmpl_id>', methods=['POST'])
def delete(tmpl_id):
    db = get_db()
    row = db.execute('SELECT name FROM msg_templates WHERE id=?', (tmpl_id,)).fetchone()
    if row:
        db.execute('DELETE FROM msg_templates WHERE id=?', (tmpl_id,))
        db.commit()
        flash(f'Template "{row[0]}" deleted.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/preview/<int:tmpl_id>')
def preview(tmpl_id):
    db = get_db()
    row = db.execute('SELECT body_markdown FROM msg_templates WHERE id=?', (tmpl_id,)).fetchone()
    if not row:
        return '', 404
    return _markdown(row['body_markdown'])
```

- [ ] **Step 5: Update web_app/templates/msg_templates.html**

```html
{% extends "base.html" %}
{% block title %}Templates — SMS App{% endblock %}
{% block content %}
<h1>Message Templates</h1>

<button class="btn btn-primary" style="margin-bottom:20px" onclick="document.getElementById('new-form').style.display='block';this.style.display='none'">+ New Template</button>

<div id="new-form" class="card" style="display:none">
  <h2>New Template</h2>
  <form method="post" action="{{ url_for('msg_templates.create') }}">
    <label>Name</label>
    <input type="text" name="name" required>
    <label>Message (Markdown)</label>
    <div style="display:flex;gap:12px;margin-top:4px">
      <textarea name="body_markdown" rows="8" style="flex:1;font-family:monospace"
        oninput="updatePreview(this.value, 'new-preview')"></textarea>
      <div style="flex:1">
        <div class="label" style="margin-bottom:6px">Preview</div>
        <div class="md-preview" id="new-preview"></div>
      </div>
    </div>
    <div style="margin-top:14px;display:flex;gap:8px">
      <button type="submit" class="btn btn-primary">Save</button>
      <button type="button" class="btn btn-secondary" onclick="document.getElementById('new-form').style.display='none'">Cancel</button>
    </div>
  </form>
</div>

{% if templates %}
{% for t in templates %}
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <strong>{{ t['name'] }}</strong>
    <div style="display:flex;gap:6px">
      <button class="btn btn-secondary btn-sm" onclick="toggleEditTmpl({{ t['id'] }})">Edit</button>
      <form method="post" action="{{ url_for('msg_templates.delete', tmpl_id=t['id']) }}" style="display:inline" onsubmit="return confirm('Delete this template?')">
        <button type="submit" class="btn btn-danger btn-sm">Delete</button>
      </form>
    </div>
  </div>
  <div class="md-preview">{{ markdown(t['body_markdown']) | safe }}</div>

  <div id="edit-tmpl-{{ t['id'] }}" style="display:none;margin-top:14px">
    <form method="post" action="{{ url_for('msg_templates.edit', tmpl_id=t['id']) }}">
      <label>Name</label>
      <input type="text" name="name" value="{{ t['name'] }}" required>
      <label>Message (Markdown)</label>
      <div style="display:flex;gap:12px;margin-top:4px">
        <textarea name="body_markdown" rows="6" style="flex:1;font-family:monospace"
          oninput="updatePreview(this.value, 'edit-preview-{{ t['id'] }}')">{{ t['body_markdown'] }}</textarea>
        <div style="flex:1">
          <div class="label" style="margin-bottom:6px">Preview</div>
          <div class="md-preview" id="edit-preview-{{ t['id'] }}">{{ markdown(t['body_markdown']) | safe }}</div>
        </div>
      </div>
      <div style="margin-top:14px;display:flex;gap:8px">
        <button type="submit" class="btn btn-primary">Save</button>
        <button type="button" class="btn btn-secondary" onclick="toggleEditTmpl({{ t['id'] }})">Cancel</button>
      </div>
    </form>
  </div>
</div>
{% endfor %}
{% else %}
<p style="color:#64748b">No templates yet. Create one above.</p>
{% endif %}

<script>
function toggleEditTmpl(id) {
  const d = document.getElementById('edit-tmpl-' + id);
  d.style.display = d.style.display === 'none' ? 'block' : 'none';
}

function updatePreview(markdown, previewId) {
  // Client-side preview via marked.js (CDN) for instant feedback
  if (window.marked) {
    document.getElementById(previewId).innerHTML = marked.parse(markdown);
  }
}
</script>
<!-- marked.js for live client-side preview -->
<script src="https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js" integrity="sha384-948ahk4ZmxYVYOc+rxN1H2gM1EJ2Duhp7uHtZ4WSLkV4Vtx5MUqnV+l7u9B+jFv+" crossorigin="anonymous"></script>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/routes/test_msg_templates.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web_app/routes/msg_templates.py web_app/templates/msg_templates.html tests/routes/test_msg_templates.py
git commit -m "feat: message templates — markdown editor, live preview, CRUD"
```

---

## Task 9: Send Page

**Files:**
- Modify: `web_app/routes/send.py`
- Modify: `web_app/templates/send.html`
- Create: `tests/routes/test_send.py`

- [ ] **Step 1: Write failing tests**

Create `tests/routes/test_send.py`:

```python
import json
from unittest.mock import patch
from datetime import datetime, timezone


def _add_contact(client, name, phone, group=''):
    client.post('/contacts/add', data={'name': name, 'phone': phone, 'group_name': group})


def test_send_page_loads(client):
    response = client.get('/send/')
    assert response.status_code == 200


def test_send_page_shows_contacts(client):
    _add_contact(client, 'Alice', '5551234567')
    response = client.get('/send/')
    assert b'Alice' in response.data


def test_send_to_individual_success(client, app):
    _add_contact(client, 'Bob', '5559876543')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Bob'").fetchone()[0]

    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result):
        response = client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Hello Bob!',
        }, follow_redirects=True)
    assert response.status_code == 200
    assert b'sent' in response.data.lower() or b'success' in response.data.lower()


def test_send_logs_to_history(client, app):
    _add_contact(client, 'Carol', '5553334444')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Carol'").fetchone()[0]

    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result):
        client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Logged message',
        })

    with app.app_context():
        from web_app.db import get_db
        row = get_db().execute("SELECT * FROM messages WHERE message='Logged message'").fetchone()
    assert row is not None
    assert row['status'] == 'sent'


def test_send_logs_failure(client, app):
    _add_contact(client, 'Dave', '5550001111')
    with app.app_context():
        from web_app.db import get_db
        contact_id = get_db().execute("SELECT id FROM contacts WHERE name='Dave'").fetchone()[0]

    mock_result = {'success': False, 'error': 'timeout'}
    with patch('web_app.routes.send.send_sms', return_value=mock_result):
        client.post('/send/', data={
            'recipient_type': 'contact',
            'contact_id': str(contact_id),
            'message': 'Will fail',
        })

    with app.app_context():
        from web_app.db import get_db
        row = get_db().execute("SELECT * FROM messages WHERE message='Will fail'").fetchone()
    assert row['status'] == 'failed'
    assert 'timeout' in row['error']


def test_send_to_manual_number(client):
    mock_result = {'success': True, 'error': None, 'data': {}}
    with patch('web_app.routes.send.send_sms', return_value=mock_result):
        response = client.post('/send/', data={
            'recipient_type': 'manual',
            'manual_phone': '5557778888',
            'message': 'Manual send',
        }, follow_redirects=True)
    assert response.status_code == 200


def test_send_empty_message_rejected(client):
    response = client.post('/send/', data={
        'recipient_type': 'manual',
        'manual_phone': '5557778888',
        'message': '',
    }, follow_redirects=True)
    assert b'Message cannot be empty' in response.data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/routes/test_send.py -v
```

Expected: FAIL — stub send route has no POST handler.

- [ ] **Step 3: Update web_app/routes/send.py**

```python
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..db import get_db
from ..textbee import send_sms, normalize_phone
from ..routes.settings import _read_env
import mistune

bp = Blueprint('send', __name__, url_prefix='/send')
_markdown = mistune.create_markdown()


@bp.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    contacts = db.execute('SELECT id, name, phone, group_name FROM contacts ORDER BY name').fetchall()
    groups = db.execute(
        'SELECT DISTINCT group_name FROM contacts WHERE group_name IS NOT NULL AND group_name != "" ORDER BY group_name'
    ).fetchall()
    templates = db.execute('SELECT id, name, body_markdown FROM msg_templates ORDER BY name').fetchall()

    if request.method == 'POST':
        return _handle_send(db, contacts, groups, templates)

    return render_template('send.html', contacts=contacts,
                           groups=[r[0] for r in groups],
                           templates=templates, markdown=_markdown)


def _handle_send(db, contacts, groups, templates):
    recipient_type = request.form.get('recipient_type', 'manual')
    message = request.form.get('message', '').strip()

    if not message:
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('send.index'))

    recipients = []
    if recipient_type == 'contact':
        contact_id = request.form.get('contact_id')
        row = db.execute('SELECT phone FROM contacts WHERE id=?', (contact_id,)).fetchone()
        if not row:
            flash('Contact not found.', 'error')
            return redirect(url_for('send.index'))
        recipients = [row['phone']]
    elif recipient_type == 'group':
        group_name = request.form.get('group_name', '')
        rows = db.execute('SELECT phone FROM contacts WHERE group_name=?', (group_name,)).fetchall()
        if not rows:
            flash('No contacts in that group.', 'error')
            return redirect(url_for('send.index'))
        recipients = [r['phone'] for r in rows]
    elif recipient_type == 'manual':
        phone = request.form.get('manual_phone', '').strip()
        if not phone:
            flash('Phone number is required.', 'error')
            return redirect(url_for('send.index'))
        recipients = [normalize_phone(phone)]

    env = _read_env(current_app.config.get('ENV_FILE'))
    api_key = env.get('TEXTBEE_API_KEY', '')
    device_id = env.get('TEXTBEE_DEVICE_ID', '')

    if not api_key or not device_id:
        flash('Textbee credentials not configured. Visit Settings.', 'error')
        return redirect(url_for('send.index'))

    result = send_sms(api_key, device_id, recipients, message)

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        'INSERT INTO messages (recipients, message, sent_at, status, error) VALUES (?, ?, ?, ?, ?)',
        (json.dumps(recipients), message, now,
         'sent' if result['success'] else 'failed',
         result.get('error'))
    )
    db.commit()

    if result['success']:
        flash(f'Message sent to {len(recipients)} recipient(s).', 'success')
    else:
        flash(f'Send failed: {result["error"]}', 'error')

    return redirect(url_for('send.index'))
```

- [ ] **Step 4: Update web_app/templates/send.html**

```html
{% extends "base.html" %}
{% block title %}Send — SMS App{% endblock %}
{% block content %}
<h1>Send a Message</h1>

<div class="card">
  <form method="post">
    <label>Recipient</label>
    <div style="display:flex;gap:10px;margin-top:4px;flex-wrap:wrap">
      <label style="margin:0;display:flex;align-items:center;gap:6px;font-weight:normal">
        <input type="radio" name="recipient_type" value="contact" onchange="showRecipient(this.value)"> Contact
      </label>
      <label style="margin:0;display:flex;align-items:center;gap:6px;font-weight:normal">
        <input type="radio" name="recipient_type" value="group" onchange="showRecipient(this.value)"> Group
      </label>
      <label style="margin:0;display:flex;align-items:center;gap:6px;font-weight:normal">
        <input type="radio" name="recipient_type" value="manual" checked onchange="showRecipient(this.value)"> Manual number
      </label>
    </div>

    <div id="r-contact" style="display:none;margin-top:8px">
      <select name="contact_id">
        <option value="">— Select contact —</option>
        {% for c in contacts %}
        <option value="{{ c['id'] }}">{{ c['name'] }} ({{ c['phone'] }})</option>
        {% endfor %}
      </select>
    </div>

    <div id="r-group" style="display:none;margin-top:8px">
      <select name="group_name">
        <option value="">— Select group —</option>
        {% for g in groups %}
        <option value="{{ g }}">{{ g }}</option>
        {% endfor %}
      </select>
    </div>

    <div id="r-manual" style="margin-top:8px">
      <input type="text" name="manual_phone" placeholder="+1XXXXXXXXXX or 10 digits">
    </div>

    <label style="margin-top:16px">Template (optional)</label>
    <select name="template_id" onchange="loadTemplate(this.value)">
      <option value="">— None, I'll type my message —</option>
      {% for t in templates %}
      <option value="{{ t['id'] }}" data-body="{{ t['body_markdown'] }}">{{ t['name'] }}</option>
      {% endfor %}
    </select>

    <label style="margin-top:12px">Message</label>
    <div style="display:flex;gap:12px;margin-top:4px">
      <textarea id="message-body" name="message" rows="8" style="flex:1;font-family:monospace"
        oninput="updatePreview(this.value)"></textarea>
      <div style="flex:1">
        <div class="label" style="margin-bottom:6px">Preview</div>
        <div class="md-preview" id="msg-preview"></div>
      </div>
    </div>

    <div style="margin-top:16px">
      <button type="submit" class="btn btn-primary">Send SMS</button>
    </div>
  </form>
</div>

<script src="https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js" integrity="sha384-948ahk4ZmxYVYOc+rxN1H2gM1EJ2Duhp7uHtZ4WSLkV4Vtx5MUqnV+l7u9B+jFv+" crossorigin="anonymous"></script>
<script>
function showRecipient(type) {
  ['contact','group','manual'].forEach(t => {
    document.getElementById('r-' + t).style.display = t === type ? 'block' : 'none';
  });
}

function loadTemplate(id) {
  const opt = document.querySelector(`[name=template_id] option[value="${id}"]`);
  if (opt && opt.dataset.body) {
    document.getElementById('message-body').value = opt.dataset.body;
    updatePreview(opt.dataset.body);
  }
}

function updatePreview(md) {
  if (window.marked) {
    document.getElementById('msg-preview').innerHTML = marked.parse(md);
  }
}
</script>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/routes/test_send.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web_app/routes/send.py web_app/templates/send.html tests/routes/test_send.py
git commit -m "feat: send page — contact/group/manual recipients, template picker, history logging"
```

---

## Task 10: History Page

**Files:**
- Modify: `web_app/routes/history.py`
- Modify: `web_app/templates/history.html`
- Create: `tests/routes/test_history.py`

- [ ] **Step 1: Write failing tests**

Create `tests/routes/test_history.py`:

```python
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


def test_history_page_loads(client):
    response = client.get('/history/')
    assert response.status_code == 200


def test_history_shows_sent_message(client, app):
    _insert_message(app, ['+15551234567'], 'Test message')
    response = client.get('/history/')
    assert b'Test message' in response.data


def test_history_shows_status(client, app):
    _insert_message(app, ['+15551234567'], 'Good msg', status='sent')
    _insert_message(app, ['+15559876543'], 'Bad msg', status='failed', error='timeout')
    response = client.get('/history/')
    assert b'sent' in response.data
    assert b'failed' in response.data


def test_history_filter_by_status(client, app):
    _insert_message(app, ['+15551234567'], 'Only sent', status='sent')
    _insert_message(app, ['+15559876543'], 'Only failed', status='failed')
    response = client.get('/history/?status=failed')
    assert b'Only failed' in response.data
    assert b'Only sent' not in response.data


def test_history_newest_first(client, app):
    import time
    _insert_message(app, ['+15551111111'], 'First message')
    time.sleep(0.01)
    _insert_message(app, ['+15552222222'], 'Second message')
    response = client.get('/history/')
    content = response.data.decode()
    assert content.index('Second message') < content.index('First message')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/routes/test_history.py -v
```

Expected: FAIL — stub history route returns empty page.

- [ ] **Step 3: Update web_app/routes/history.py**

```python
import json
from flask import Blueprint, render_template, request
from ..db import get_db

bp = Blueprint('history', __name__, url_prefix='/history')


@bp.route('/')
def index():
    db = get_db()
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = 'SELECT id, recipients, message, sent_at, status, error FROM messages'
    params = []
    conditions = []

    if status_filter in ('sent', 'failed'):
        conditions.append('status = ?')
        params.append(status_filter)
    if date_from:
        conditions.append('sent_at >= ?')
        params.append(date_from)
    if date_to:
        conditions.append('sent_at <= ?')
        params.append(date_to + 'T23:59:59')

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY sent_at DESC'

    rows = db.execute(query, params).fetchall()

    messages = []
    for row in rows:
        recipients = json.loads(row['recipients'])
        messages.append({
            'id': row['id'],
            'recipients': recipients,
            'recipient_display': ', '.join(recipients[:3]) + (f' +{len(recipients)-3} more' if len(recipients) > 3 else ''),
            'message': row['message'],
            'message_preview': row['message'][:80] + ('…' if len(row['message']) > 80 else ''),
            'sent_at': row['sent_at'],
            'status': row['status'],
            'error': row['error'],
        })

    return render_template('history.html', messages=messages,
                           status_filter=status_filter,
                           date_from=date_from, date_to=date_to)
```

- [ ] **Step 4: Update web_app/templates/history.html**

```html
{% extends "base.html" %}
{% block title %}History — SMS App{% endblock %}
{% block content %}
<h1>Message History</h1>

<div class="card" style="padding:14px">
  <form method="get" style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end">
    <div>
      <label>Status</label>
      <select name="status">
        <option value="" {% if not status_filter %}selected{% endif %}>All</option>
        <option value="sent" {% if status_filter == 'sent' %}selected{% endif %}>Sent</option>
        <option value="failed" {% if status_filter == 'failed' %}selected{% endif %}>Failed</option>
      </select>
    </div>
    <div>
      <label>From</label>
      <input type="date" name="date_from" value="{{ date_from }}">
    </div>
    <div>
      <label>To</label>
      <input type="date" name="date_to" value="{{ date_to }}">
    </div>
    <button type="submit" class="btn btn-secondary">Filter</button>
    <a href="{{ url_for('history.index') }}" class="btn btn-secondary">Clear</a>
  </form>
</div>

{% if messages %}
<div class="card" style="padding:0">
  <table>
    <thead>
      <tr><th>Date / Time</th><th>Recipient(s)</th><th>Message</th><th>Status</th></tr>
    </thead>
    <tbody>
    {% for m in messages %}
    <tr onclick="toggleDetail('detail-{{ m.id }}')" style="cursor:pointer">
      <td style="white-space:nowrap;font-size:12px">{{ m.sent_at[:16].replace('T', ' ') }}</td>
      <td style="font-size:12px">{{ m.recipient_display }}</td>
      <td style="color:#475569">{{ m.message_preview }}</td>
      <td>
        <span style="font-size:12px;padding:2px 8px;border-radius:10px;
          background:{% if m.status == 'sent' %}#dcfce7;color:#166534{% else %}#fee2e2;color:#991b1b{% endif %}">
          {{ m.status }}
        </span>
      </td>
    </tr>
    <tr id="detail-{{ m.id }}" style="display:none;background:#f8fafc">
      <td colspan="4" style="padding:12px;font-size:13px">
        <strong>Full message:</strong>
        <pre style="margin-top:6px;white-space:pre-wrap;font-family:inherit">{{ m.message }}</pre>
        {% if m.error %}
        <p style="margin-top:8px;color:#991b1b"><strong>Error:</strong> {{ m.error }}</p>
        {% endif %}
        <p style="margin-top:8px;color:#64748b;font-size:12px">To: {{ ', '.join(m.recipients) }}</p>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<p style="color:#64748b">No messages yet.</p>
{% endif %}

<script>
function toggleDetail(id) {
  const row = document.getElementById(id);
  row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
}
</script>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/routes/test_history.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web_app/routes/history.py web_app/templates/history.html tests/routes/test_history.py
git commit -m "feat: history page — message log, status filter, date filter, expandable rows"
```

---

## Task 11: Google Contacts Sync

**Files:**
- Create: `web_app/google_sync.py`
- Modify: `web_app/routes/settings.py`
- Modify: `web_app/routes/contacts.py`
- Create: `tests/test_google_sync.py`

- [ ] **Step 1: Fetch google-auth-oauthlib docs via Context7**

Use Context7 MCP:
- `resolve-library-id` → search "google-auth-oauthlib"
- `query-docs` → "InstalledAppFlow from_client_secrets_file run_local_server credentials token"

Then:
- `resolve-library-id` → search "google-api-python-client"
- `query-docs` → "build People API connections list resourceName phoneNumbers"

- [ ] **Step 2: Write failing tests**

Create `tests/test_google_sync.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock


def _make_person(name, phone):
    return {
        'names': [{'displayName': name}],
        'phoneNumbers': [{'value': phone}],
    }


def test_extract_contacts_from_google_response():
    from web_app.google_sync import extract_contacts
    people = [
        _make_person('Alice Green', '+15551234567'),
        _make_person('Bob Blue', '5559876543'),
        {'names': [{'displayName': 'No Phone'}]},  # no phoneNumbers key
    ]
    contacts = extract_contacts(people)
    assert len(contacts) == 2
    assert contacts[0] == ('Alice Green', '+15551234567')
    assert contacts[1][0] == 'Bob Blue'


def test_extract_contacts_skips_no_phone():
    from web_app.google_sync import extract_contacts
    people = [{'names': [{'displayName': 'Ghost'}]}]
    contacts = extract_contacts(people)
    assert contacts == []


def test_merge_contacts_inserts_new(app):
    from web_app.google_sync import merge_contacts
    from web_app.db import get_db
    with app.app_context():
        merge_contacts(get_db(), [('New Person', '+15550001111')])
        row = get_db().execute("SELECT * FROM contacts WHERE name='New Person'").fetchone()
    assert row is not None
    assert row['phone'] == '+15550001111'


def test_merge_contacts_updates_name_on_match(app):
    from web_app.db import get_db
    from web_app.google_sync import merge_contacts
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO contacts (name, phone, group_name) VALUES ('Old Name', '+15552223333', NULL)")
        db.commit()
        merge_contacts(db, [('Google Name', '+15552223333')])
        row = db.execute("SELECT name FROM contacts WHERE phone='+15552223333'").fetchone()
    assert row['name'] == 'Google Name'


def test_merge_contacts_no_duplicate(app):
    from web_app.db import get_db
    from web_app.google_sync import merge_contacts
    with app.app_context():
        db = get_db()
        merge_contacts(db, [('Alice', '+15554445555')])
        merge_contacts(db, [('Alice', '+15554445555')])
        count = db.execute("SELECT COUNT(*) FROM contacts WHERE phone='+15554445555'").fetchone()[0]
    assert count == 1
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_google_sync.py -v
```

Expected: ImportError — web_app.google_sync doesn't exist.

- [ ] **Step 4: Create web_app/google_sync.py**

```python
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .textbee import normalize_phone

SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.json')
CLIENT_SECRET_ENV_KEY = 'GOOGLE_CLIENT_SECRET_FILE'


def get_token_path():
    return TOKEN_FILE


def is_connected():
    return os.path.exists(TOKEN_FILE)


def disconnect():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def get_credentials():
    """Load credentials from token.json. Returns None if not connected."""
    if not os.path.exists(TOKEN_FILE):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return creds


def start_oauth_flow(client_secret_file: str, redirect_uri: str):
    """
    Start the OAuth flow and return the authorization URL.
    The flow object should be persisted in session for the callback.
    Returns: (auth_url, state)
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file, SCOPES, redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true'
    )
    return auth_url, state, flow


def fetch_google_contacts(creds) -> list:
    """
    Fetch all contacts with phone numbers from Google People API.
    Returns a list of raw person dicts.
    """
    service = build('people', 'v1', credentials=creds)
    people = []
    page_token = None

    while True:
        kwargs = {
            'resourceName': 'people/me',
            'pageSize': 1000,
            'personFields': 'names,phoneNumbers',
        }
        if page_token:
            kwargs['pageToken'] = page_token

        result = service.people().connections().list(**kwargs).execute()
        people.extend(result.get('connections', []))
        page_token = result.get('nextPageToken')
        if not page_token:
            break

    return people


def extract_contacts(people: list) -> list[tuple[str, str]]:
    """
    Extract (name, normalized_phone) tuples from Google People API response.
    Skips people with no phone numbers.
    """
    contacts = []
    for person in people:
        phone_numbers = person.get('phoneNumbers', [])
        if not phone_numbers:
            continue
        names = person.get('names', [])
        name = names[0]['displayName'] if names else 'Unknown'
        phone = normalize_phone(phone_numbers[0]['value'])
        contacts.append((name, phone))
    return contacts


def merge_contacts(db, contacts: list[tuple[str, str]]) -> int:
    """
    Insert or update contacts in the local DB.
    Matches on normalized phone number. Google name wins on conflict.
    Returns count of upserted rows.
    """
    count = 0
    for name, phone in contacts:
        existing = db.execute('SELECT id FROM contacts WHERE phone=?', (phone,)).fetchone()
        if existing:
            db.execute('UPDATE contacts SET name=? WHERE id=?', (name, existing['id']))
        else:
            db.execute(
                'INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, NULL)',
                (name, phone)
            )
        count += 1
    db.commit()
    return count
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_google_sync.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Add Google OAuth routes to web_app/routes/settings.py**

Add these routes to the existing `settings.py` (append after the existing `test_connection` route):

```python
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
    # Store flow credentials info in session
    session['google_oauth_state'] = state
    session['google_client_secret_file'] = client_secret_file
    from flask import redirect as flask_redirect
    return flask_redirect(auth_url)


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
```

- [ ] **Step 7: Add Google sync trigger to web_app/routes/contacts.py**

Add this route to the existing `contacts.py` (append after `import_csv`):

```python
@bp.route('/google-sync')
def google_sync():
    from ..google_sync import is_connected, get_credentials, fetch_google_contacts, extract_contacts, merge_contacts
    if not is_connected():
        flash('Google account not connected. Visit Settings to connect.', 'error')
        return redirect(url_for('contacts.index'))

    creds = get_credentials()
    try:
        people = fetch_google_contacts(creds)
        contacts = extract_contacts(people)
        db = get_db()
        count = merge_contacts(db, contacts)
        flash(f'Synced {count} contacts from Google.', 'success')
    except Exception as e:
        flash(f'Google sync failed: {e}', 'error')

    return redirect(url_for('contacts.index'))
```

- [ ] **Step 8: Add GOOGLE_CLIENT_SECRET_FILE field to settings.html**

In `web_app/templates/settings.html`, add a third field inside the Textbee credentials form, after the Device ID field:

```html
    <label>Google OAuth Credentials File (path)</label>
    <input type="text" name="google_client_secret_file" value="{{ env.get('GOOGLE_CLIENT_SECRET_FILE', '') }}" placeholder="/path/to/client_secret.json">
```

And add this to the `settings.py` POST handler — after writing `device_id`, add:

```python
google_file = request.form.get('google_client_secret_file', '').strip()
_write_env(env_file, 'GOOGLE_CLIENT_SECRET_FILE', google_file)
```

- [ ] **Step 9: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add web_app/google_sync.py web_app/routes/settings.py web_app/routes/contacts.py web_app/templates/settings.html tests/test_google_sync.py
git commit -m "feat: Google Contacts sync — OAuth flow, People API fetch, upsert merge"
```

---

## Task 12: Final Smoke Test + README

**Files:**
- Create: `web_app/README.md` (instructions for running)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS. Fix any failures before proceeding.

- [ ] **Step 2: Manual smoke test**

```bash
python web_app/app.py
```

Verify each page in the browser:
- [ ] http://localhost:5000 → redirects to /send/
- [ ] /send/ — loads, recipient selector works, markdown preview works
- [ ] /contacts/ — loads, add a contact, it appears in table
- [ ] /templates/ — create a template, appears in list with preview
- [ ] /history/ — shows history after sending a test message
- [ ] /settings/ — loads, save credentials, test connection button visible
- [ ] /help/ — all sections present

Stop server with Ctrl+C.

- [ ] **Step 3: Update root README.md with web app section**

Add the following section to the existing `README.md`:

```markdown
## Web App

A browser-based interface for the same SMS functionality, running locally alongside this CLI app.

### Setup

```bash
pip install -r requirements.txt
```

### Run

```bash
python web_app/app.py
```

Open **http://localhost:5000** in your browser.

Both apps share `contacts.db` — contacts added in either app are visible in both.

### Google Contacts Setup

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. Click **Connect Google Account** to authorize
```

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add web app setup and Google Contacts instructions to README"
```

---

## All Tests

Run the complete test suite at any time:

```bash
pytest tests/ -v
```

Expected coverage:
- `test_db.py` — 6 tests
- `test_textbee.py` — 6 tests
- `test_google_sync.py` — 5 tests
- `routes/test_help.py` — 3 tests
- `routes/test_settings.py` — 3 tests
- `routes/test_contacts.py` — 7 tests
- `routes/test_msg_templates.py` — 5 tests
- `routes/test_send.py` — 7 tests
- `routes/test_history.py` — 5 tests

**Total: 47 tests**

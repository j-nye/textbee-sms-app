# Semgrep Findings Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every open finding in the 2026-09-04 Semgrep scan of `j-nye/textbee-sms-app` (commit `f232fe90f8a8fb587c40f518a5639c03a392e54f`) — either by fixing the underlying issue or, where Semgrep's own autotriage and a manual code read confirm a false positive, by suppressing it with a documented `nosemgrep` annotation.

**Architecture:** No architectural changes. This is a remediation pass: two real code/config fixes (Dependabot cooldown, GitHub Actions SHA pinning, and a Host-header-injection fix in the Google OAuth flow) plus documented `nosemgrep` suppressions for confirmed false positives (Jinja/Flask CSRF tokens that a Django-specific rule doesn't recognize, and three low-confidence urllib matches on hardcoded-host URLs).

**Tech Stack:** Python 3.10–3.13, Flask 3.x, Flask-WTF (CSRFProtect), pytest, GitHub Actions, Dependabot.

**Spec:** `/Users/jason/Downloads/Semgrep_Code_Combined_Findings_2026_09_04.csv` (22 findings covering 5 distinct rules)

## Global Constraints

- `pytest -q` must pass after every task (this is what CI runs — see `.github/workflows/tests.yml`).
- Do not weaken or disable Flask-WTF's `CSRFProtect` (`web_app/app.py:57`).
- Every `nosemgrep` suppression must reference the exact rule ID and include a one-line justification comment, per Semgrep's documented convention (`nosemgrep: <rule-id>`, comment on the line before the flagged line).
- Pin GitHub Actions to the latest patch SHA of the **currently pinned major version** (v4 for `actions/checkout`, v5 for `actions/setup-python`) — no unplanned major-version bump — with the human-readable version kept in a trailing `# vX.Y.Z` comment.
- New Settings fields must match the existing label/input markup style in `web_app/templates/settings.html`.

---

## Findings Triage Summary

| # | Rule | File(s) | Verdict | Resolution |
|---|------|---------|---------|------------|
| 1 | `dependabot-missing-cooldown` | `.github/dependabot.yml` | True positive | Add `cooldown.default-days: 7` |
| 2 | `django-no-csrf-token` (×14) | 7 templates | **False positive** — `CSRFProtect(app)` is active app-wide and every form already carries `{{ csrf_token() }}`; the rule only recognizes Django's `{% csrf_token %}` tag, not Jinja/Flask's function call | `nosemgrep` + justification comment on each form |
| 3 | `flask-url-for-external-true` (×2) | `web_app/routes/settings.py:110,130` | True positive | Stop deriving the OAuth redirect URI from the request `Host` header; use an operator-configured `APP_BASE_URL` instead |
| 4 | `dynamic-urllib-use-detected` (×3) | `sms.py:67`, `web_app/routes/settings.py:85`, `web_app/textbee.py:47` | **False positive** — URL host is a hardcoded literal (`api.textbee.dev`); only a path segment (`device_id`) is interpolated, so scheme/host can't be attacker-controlled | `nosemgrep` + justification comment |
| 5 | `github-actions-mutable-action-tag` (×2) | `.github/workflows/tests.yml:17,20` | True positive | Pin to commit SHA + version comment |

---

### Task 1: Add Dependabot cooldown (and a `github-actions` ecosystem entry)

**Files:**
- Modify: `.github/dependabot.yml`

**Interfaces:** None (pure YAML config).

- [ ] **Step 1: Add the missing `cooldown` block to the existing `pip` entry, and add a `github-actions` ecosystem entry with its own cooldown**

The finding (`dependabot-missing-cooldown`, `.github/dependabot.yml#L3`) flags the `pip` entry for having no `cooldown` block, which means newly-published package versions can be proposed immediately instead of after a waiting period. Fix that, and also register the `github-actions` ecosystem — Task 2 below pins the two workflow actions to commit SHAs, and without a Dependabot entry for `github-actions`, those pinned SHAs would never get automatic version-bump PRs going forward.

Replace the full contents of `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    cooldown:
      default-days: 7

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
```

- [ ] **Step 2: Validate the YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "fix(security): add Dependabot cooldown period, add github-actions ecosystem"
```

---

### Task 2: Pin GitHub Actions to commit SHAs

**Files:**
- Modify: `.github/workflows/tests.yml:17`, `.github/workflows/tests.yml:20`

**Interfaces:** None.

Findings `github-actions-mutable-action-tag` (`tests.yml#L17`, `tests.yml#L20`) flag `actions/checkout@v4` and `actions/setup-python@v5` as mutable references — a tag can be silently repointed by the action owner (as happened in the `tj-actions/changed-files` and `reviewdog/action-*` supply-chain incidents). Pin both to the commit SHA of their latest current patch release, keeping the version visible in a trailing comment.

Verified against the GitHub API on 2026-09-04:
- `actions/checkout` latest `v4.x` release is `v4.4.0` → `11d5960a326750d5838078e36cf38b85af677262`
- `actions/setup-python` latest `v5.x` release is `v5.6.0` → `a26af69be951a213d495a4c3e4e4022e16d87065`

- [ ] **Step 1: Pin `actions/checkout`**

In `.github/workflows/tests.yml`, change:

```yaml
      - uses: actions/checkout@v4
```

to:

```yaml
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
```

- [ ] **Step 2: Pin `actions/setup-python`**

In the same file, change:

```yaml
        uses: actions/setup-python@v5
```

to:

```yaml
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
```

- [ ] **Step 3: Validate the YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "fix(security): pin GitHub Actions to commit SHAs"
```

---

### Task 3: Suppress the `django-no-csrf-token` false positives (14 locations, 8 files)

**Files:**
- Modify: `web_app/templates/base.html:20`
- Modify: `web_app/templates/change_password.html:7`
- Modify: `web_app/templates/contacts.html:9,17,33,52,60`
- Modify: `web_app/templates/login.html:6`
- Modify: `web_app/templates/msg_templates.html:10,37,46`
- Modify: `web_app/templates/settings.html:9,40`
- Modify: `web_app/templates/setup.html:7`

**Interfaces:** None (template annotations only, no rendered output changes — `{# ... #}` is a Jinja comment, stripped before the page reaches the browser).

**Why these are false positives:** `web_app/app.py:57` calls `CSRFProtect(app)`, which protects every state-changing route app-wide. Every `<form method="post">` in this codebase already carries `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. The Semgrep rule `python.django.security.django-no-csrf-token.django-no-csrf-token` only recognizes Django's `{% csrf_token %}` template tag or Django-specific form attributes — it doesn't know about Flask-WTF's `{{ csrf_token() }}` call, so it flags every form in this Flask/Jinja app. Semgrep's own autotriage already reached this conclusion for 3 of the 14 (`settings.html:9`, `settings.html:40`, `setup.html:7`); the same reasoning applies identically to the other 11, since every form in the app uses the exact same pattern.

Use this exact suppression comment (same rule ID, same wording) at every location, placed on the line immediately before the `<form ...>` tag, matching that line's indentation:

```jinja
{# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
```

- [ ] **Step 1: `web_app/templates/base.html`**

Change:
```html
        <form method="post" action="{{ url_for('auth.logout') }}" class="nav-logout">
```
to:
```html
        {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
        <form method="post" action="{{ url_for('auth.logout') }}" class="nav-logout">
```

- [ ] **Step 2: `web_app/templates/change_password.html`**

Change:
```html
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Current Password</label>
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Current Password</label>
```

- [ ] **Step 3: `web_app/templates/contacts.html` — all 5 forms**

Change:
```html
  <form method="post" action="{{ url_for('contacts.google_sync') }}" style="display:inline">
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post" action="{{ url_for('contacts.google_sync') }}" style="display:inline">
```

Change:
```html
  <form method="post" action="{{ url_for('contacts.add') }}">
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post" action="{{ url_for('contacts.add') }}">
```

Change:
```html
  <form method="post" action="{{ url_for('contacts.import_csv') }}" enctype="multipart/form-data">
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post" action="{{ url_for('contacts.import_csv') }}" enctype="multipart/form-data">
```

Change:
```html
        <form method="post" action="{{ url_for('contacts.delete', contact_id=c['id']) }}" style="display:inline" onsubmit="return confirm('Delete this contact?')">
```
to:
```html
        {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
        <form method="post" action="{{ url_for('contacts.delete', contact_id=c['id']) }}" style="display:inline" onsubmit="return confirm('Delete this contact?')">
```

Change:
```html
        <form method="post" action="{{ url_for('contacts.edit', contact_id=c['id']) }}">
```
to:
```html
        {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
        <form method="post" action="{{ url_for('contacts.edit', contact_id=c['id']) }}">
```

- [ ] **Step 4: `web_app/templates/login.html`**

Change:
```html
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Username</label>
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Username</label>
```

- [ ] **Step 5: `web_app/templates/msg_templates.html` — all 3 forms**

Change:
```html
  <form method="post" action="{{ url_for('msg_templates.create') }}">
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post" action="{{ url_for('msg_templates.create') }}">
```

Change:
```html
      <form method="post" action="{{ url_for('msg_templates.delete', tmpl_id=t['id']) }}" style="display:inline" onsubmit="return confirm('Delete this template?')">
```
to:
```html
      {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
      <form method="post" action="{{ url_for('msg_templates.delete', tmpl_id=t['id']) }}" style="display:inline" onsubmit="return confirm('Delete this template?')">
```

Change:
```html
    <form method="post" action="{{ url_for('msg_templates.edit', tmpl_id=t['id']) }}">
```
to:
```html
    {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
    <form method="post" action="{{ url_for('msg_templates.edit', tmpl_id=t['id']) }}">
```

- [ ] **Step 6: `web_app/templates/settings.html` — both forms**

Change:
```html
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>API Key</label>
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>API Key</label>
```

Change:
```html
    <form method="post" action="{{ url_for('settings.google_disconnect') }}" style="display:inline">
```
to:
```html
    {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
    <form method="post" action="{{ url_for('settings.google_disconnect') }}" style="display:inline">
```

- [ ] **Step 7: `web_app/templates/setup.html`**

Change:
```html
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Username</label>
```
to:
```html
  {# nosemgrep: python.django.security.django-no-csrf-token.django-no-csrf-token -- false positive: Flask-WTF CSRFProtect is enabled app-wide (web_app/app.py) and this form already sends a csrf_token() hidden field; this rule only recognizes Django's {% csrf_token %} tag. #}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Username</label>
```

- [ ] **Step 8: Verify every form still has exactly one preceding `nosemgrep` comment and the app still renders**

Run: `grep -c "nosemgrep: python.django.security.django-no-csrf-token" web_app/templates/*.html | awk -F: '{sum+=$2} END {print sum}'`
Expected: `14`

Run: `pytest -q`
Expected: all tests pass (these are non-functional Jinja comments, so no test should change behavior).

- [ ] **Step 9: Commit**

```bash
git add web_app/templates/base.html web_app/templates/change_password.html web_app/templates/contacts.html web_app/templates/login.html web_app/templates/msg_templates.html web_app/templates/settings.html web_app/templates/setup.html
git commit -m "chore(security): suppress django-no-csrf-token false positives on Flask/Jinja forms"
```

---

### Task 4: Suppress the `dynamic-urllib-use-detected` false positives (3 locations)

**Files:**
- Modify: `sms.py:67`
- Modify: `web_app/routes/settings.py:85`
- Modify: `web_app/textbee.py:47`

**Interfaces:** None (comment-only change).

**Why these are false positives:** the rule flags any `urllib.request.urlopen()` call on a `Request` built from a "dynamic" value, in case that value lets an attacker choose an arbitrary URL scheme (e.g. `file://`). In all three locations, the URL is built from a hardcoded HTTPS host (`https://api.textbee.dev/...`) with only a path segment (`device_id`) interpolated — the scheme and host are fixed string literals, so no dynamic input can redirect the request to `file://` or another host.

- [ ] **Step 1: `sms.py`**

Change:
```python
    try:
        with urllib.request.urlopen(req) as response:
```
to:
```python
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- false positive: url is built from a fixed https://api.textbee.dev host template; only device_id (a path segment) is interpolated, so the scheme/host can't be attacker-controlled.
        with urllib.request.urlopen(req) as response:
```

- [ ] **Step 2: `web_app/routes/settings.py`**

Change:
```python
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        urllib.request.urlopen(req)
```
to:
```python
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- false positive: url is built from a fixed https://api.textbee.dev host template; only device_id (a path segment) is interpolated, so the scheme/host can't be attacker-controlled.
        urllib.request.urlopen(req)
```

- [ ] **Step 3: `web_app/textbee.py`**

Change:
```python
    try:
        with urllib.request.urlopen(req) as response:
```
to:
```python
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- false positive: url is built from a fixed https://api.textbee.dev host template; only device_id (a path segment) is interpolated, so the scheme/host can't be attacker-controlled.
        with urllib.request.urlopen(req) as response:
```

- [ ] **Step 4: Verify and run tests**

Run: `grep -c "nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected" sms.py web_app/routes/settings.py web_app/textbee.py | awk -F: '{sum+=$2} END {print sum}'`
Expected: `3`

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add sms.py web_app/routes/settings.py web_app/textbee.py
git commit -m "chore(security): suppress dynamic-urllib-use-detected false positives on fixed-host requests"
```

---

### Task 5: Fix Host-header-derived OAuth redirect URI (`flask-url-for-external-true`)

**Files:**
- Modify: `web_app/routes/settings.py:8,44-65,98-114,117-149`
- Modify: `web_app/templates/settings.html:18-19`
- Modify: `tests/routes/test_settings.py`
- Modify: `README.md` (Google Contacts Setup section)

**Interfaces:**
- Produces: `_read_env()` now includes `APP_BASE_URL` in its defaults dict — later code reads it via `env.get('APP_BASE_URL', '')`.

**The problem:** `web_app/routes/settings.py:110` and `:130` build the Google OAuth `redirect_uri` with `url_for('settings.google_callback', _external=True)`. Flask builds `_external=True` URLs from the incoming request's `Host` header by default, so a request with a forged `Host` header influences the URL sent to Google as the OAuth callback target — a Host-header-injection risk. The fix: stop deriving the base URL from the request, and use an operator-configured `APP_BASE_URL` (set once in Settings, alongside the other Textbee/Google fields) instead. If it isn't configured, fail closed with a flash message rather than falling back to the request Host header.

- [ ] **Step 1: Write the failing tests**

Add to `tests/routes/test_settings.py` (append at the end of the file):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/routes/test_settings.py -v -k "base_url"`
Expected: `test_google_connect_requires_base_url`, `test_google_connect_builds_redirect_from_configured_base_url`, and `test_settings_save_persists_base_url` FAIL (current code always builds `redirect_uri` from `_external=True` and never reads/writes `APP_BASE_URL`). `test_google_callback_requires_base_url` will currently fail too, since the callback route has no `APP_BASE_URL` check yet — it will error out or produce a different flash instead of `b'OAuth session expired'` before reaching that check. Confirm all four fail before proceeding.

- [ ] **Step 3: Add `APP_BASE_URL` to `_read_env` defaults**

In `web_app/routes/settings.py`, change:

```python
def _read_env(env_file):
    values = {'TEXTBEE_API_KEY': '', 'TEXTBEE_DEVICE_ID': '', 'GOOGLE_CLIENT_SECRET_FILE': ''}
```

to:

```python
def _read_env(env_file):
    values = {'TEXTBEE_API_KEY': '', 'TEXTBEE_DEVICE_ID': '', 'GOOGLE_CLIENT_SECRET_FILE': '', 'APP_BASE_URL': ''}
```

- [ ] **Step 4: Add a shared `_google_redirect_uri` helper**

`google_connect` and `google_callback` both need to build the *exact same* redirect URI (Google's token exchange requires it), so put the logic in one place instead of duplicating it at both call sites. Add this function in `web_app/routes/settings.py` directly after `_write_env` (i.e. right before the `@bp.route('/', methods=['GET', 'POST'])` line):

```python
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
```

- [ ] **Step 5: Persist `APP_BASE_URL` from the Settings form POST**

In `web_app/routes/settings.py`, change:

```python
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        device_id = request.form.get('device_id', '').strip()
        google_file = request.form.get('google_client_secret_file', '').strip()
        try:
            _write_env(env_file, 'TEXTBEE_API_KEY', api_key)
            _write_env(env_file, 'TEXTBEE_DEVICE_ID', device_id)
            _write_env(env_file, 'GOOGLE_CLIENT_SECRET_FILE', google_file)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('settings.index'))
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))
```

to:

```python
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
```

- [ ] **Step 6: Stop deriving the redirect URI from the request `Host` header in `google_connect`**

In `web_app/routes/settings.py`, change:

```python
    if not client_secret_file or not os.path.exists(client_secret_file):
        flash('Set GOOGLE_CLIENT_SECRET_FILE in Settings to the path of your Google OAuth credentials JSON.', 'error')
        return redirect(url_for('settings.index'))

    redirect_uri = url_for('settings.google_callback', _external=True)
    auth_url, state, flow = start_oauth_flow(client_secret_file, redirect_uri)
```

to:

```python
    if not client_secret_file or not os.path.exists(client_secret_file):
        flash('Set GOOGLE_CLIENT_SECRET_FILE in Settings to the path of your Google OAuth credentials JSON.', 'error')
        return redirect(url_for('settings.index'))

    redirect_uri = _google_redirect_uri(env)
    if not redirect_uri:
        flash('Set Public Base URL in Settings before connecting Google (used to build the OAuth redirect link).', 'error')
        return redirect(url_for('settings.index'))

    auth_url, state, flow = start_oauth_flow(client_secret_file, redirect_uri)
```

- [ ] **Step 7: Use the same helper in `google_callback`**

`InstalledAppFlow` / Google's token exchange requires the `redirect_uri` passed to `fetch_token` to exactly match what was sent to Google's authorization endpoint in Step 6, so `google_callback` must compute it the same way — via the same `_google_redirect_uri` helper.

In `web_app/routes/settings.py`, change:

```python
    client_secret_file = session.get('google_client_secret_file', '')
    expected_state = session.pop('google_oauth_state', None)
    if not client_secret_file or not expected_state:
        flash('OAuth session expired. Please try again.', 'error')
        return redirect(url_for('settings.index'))

    redirect_uri = url_for('settings.google_callback', _external=True)
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file, SCOPES, redirect_uri=redirect_uri, state=expected_state
    )
```

to:

```python
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
```

- [ ] **Step 8: Add the Settings page field**

In `web_app/templates/settings.html`, change:

```html
    <label>Google OAuth Credentials File (path)</label>
    <input type="text" name="google_client_secret_file" value="{{ env.get('GOOGLE_CLIENT_SECRET_FILE', '') }}" placeholder="/path/to/client_secret.json">
    <div style="margin-top:16px;display:flex;gap:10px">
```

to:

```html
    <label>Google OAuth Credentials File (path)</label>
    <input type="text" name="google_client_secret_file" value="{{ env.get('GOOGLE_CLIENT_SECRET_FILE', '') }}" placeholder="/path/to/client_secret.json">
    <label>Public Base URL (for Google OAuth redirect)</label>
    <input type="text" name="app_base_url" value="{{ env.get('APP_BASE_URL', '') }}" placeholder="https://sms.example.com">
    <div style="margin-top:16px;display:flex;gap:10px">
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `pytest tests/routes/test_settings.py -v -k "base_url"`
Expected: all four tests PASS.

Run: `pytest -q`
Expected: full suite passes (no regressions in unrelated tests).

- [ ] **Step 10: Update README documentation**

In `README.md`, under `### Google Contacts Setup`, change:

```markdown
1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. Click **Connect Google Account** to authorize
```

to:

```markdown
1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. In the same page, set **Public Base URL** to the URL you use to reach this app (e.g. `http://192.168.1.50:5050` for LAN use, or `https://sms.example.com` behind a reverse proxy) — this is used to build the OAuth redirect link instead of trusting the request's `Host` header
7. Click **Connect Google Account** to authorize
```

- [ ] **Step 11: Commit**

```bash
git add web_app/routes/settings.py web_app/templates/settings.html tests/routes/test_settings.py README.md
git commit -m "fix(security): stop deriving Google OAuth redirect URI from request Host header"
```

---

### Task 6: Final verification pass

**Files:** None (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 2: Confirm every finding from the CSV maps to a change**

Run:
```bash
git log --oneline -6
```
Expected: 5 commits from Tasks 1–5 (Task 6 makes no commit), each addressing one row of the Findings Triage Summary table above.

- [ ] **Step 3: Push the branch and let Semgrep re-scan**

Local `semgrep scan` can't be used to confirm suppression here (this sandbox has no authenticated network access to `semgrep.dev`'s rule registry). Push this branch and open a PR — the repo's connected Semgrep GitHub integration will re-scan and should show all 22 findings as resolved: 5 fixed outright (the Dependabot cooldown, the two pinned Actions, and the two Host-header-injection call sites) plus 17 suppressed via `nosemgrep` (14 CSRF-token false positives + 3 urllib false positives), including the 3 the platform's autotriage had already flagged False positive but left Open. If any `nosemgrep` annotation doesn't take effect (e.g. if Semgrep's HTML/Jinja parsing doesn't honor `{# ... #}` the same way it does `//`/`#` in other languages), the fallback is to mark those specific findings **False positive** directly in the Semgrep AppSec Platform UI at the finding links in the CSV — the code-level suppression comments still document *why* for future readers even if the platform needs the manual triage too.

```bash
git push -u origin <branch-name>
```

(Do not run this automatically — confirm the branch name and target with the user first, per repo convention of PR-based changes.)

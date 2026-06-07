# Web SMS App — Design Spec

**Date:** 2026-06-07  
**Status:** Approved  
**Tech Stack:** Python · Flask · SQLite · Google People API  

---

## Implementation Note — Documentation

When implementing this application, **always use the Context7 MCP server** (`resolve-library-id` + `query-docs`) to fetch current documentation for all libraries before writing code. This applies to:

- **Flask** — routing, Jinja2 templates, request handling
- **google-auth-oauthlib** — OAuth 2.0 flow
- **google-api-python-client** — People API calls
- **mistune** — markdown rendering API
- **python-dotenv** — `.env` read/write

Do not rely on training-data knowledge for these libraries — fetch current docs every time.

---

## Overview

A local web application that provides a browser-based interface for sending SMS messages via the Textbee API. It runs alongside the existing `sms.py` CLI app, sharing the same `contacts.db` SQLite database. Intended for single-user, local use only (no authentication, no remote access).

---

## Architecture

```
Browser (http://localhost:5000)
        ↕  HTTP
Flask server (web_app.py)
        ↕  SQLite
contacts.db  ←→  sms.py (CLI, continues to work independently)

External services:
  - Textbee API       (SMS gateway via Android phone)
  - Google People API (contact sync, OAuth 2.0)
```

### File Structure

```
SMS-App/
├── sms.py                  # existing CLI app (unchanged)
├── contacts.db             # shared database
├── web_app/
│   ├── app.py              # Flask app factory, route registration
│   ├── db.py               # database init, shared helpers
│   ├── routes/
│   │   ├── send.py         # Send page routes
│   │   ├── contacts.py     # Contacts CRUD + Google sync
│   │   ├── templates.py    # Message template CRUD
│   │   ├── history.py      # Message history routes
│   │   ├── settings.py     # Credentials + Google OAuth
│   │   └── help.py         # Help page route
│   ├── google_sync.py      # Google People API integration
│   ├── textbee.py          # Textbee send logic (extracted from CLI)
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Sidebar layout shell
│   │   ├── send.html
│   │   ├── contacts.html
│   │   ├── templates.html
│   │   ├── history.html
│   │   ├── settings.html
│   │   └── help.html
│   └── static/
│       └── app.css         # Minimal custom styles
├── .env                    # Textbee + Google credentials (existing)
└── requirements.txt        # Flask, google-auth, mistune
```

---

## Database Schema

The existing `contacts` table is unchanged. Two new tables are added to `contacts.db`:

### `messages`
Stores every sent message for history.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| recipients | TEXT | JSON array of phone numbers |
| message | TEXT | Final rendered message text |
| sent_at | DATETIME | UTC timestamp |
| status | TEXT | `sent` / `failed` |
| error | TEXT | Error message if failed, nullable |

### `templates`
Markdown message templates.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | Display name |
| body_markdown | TEXT | Raw markdown source |
| created_at | DATETIME | UTC timestamp |
| updated_at | DATETIME | UTC timestamp |

---

## Pages & Features

### Send
- Recipient selector: search contacts by name, or select a saved group, or type a number manually
- Message composer: plain text area, or select a saved template (rendered from markdown)
- Preview: shows rendered markdown before sending
- On submit: calls Textbee API, logs result to `messages` table
- Success/failure shown inline (no full-page reload)

### Contacts
- Table listing all contacts (id, name, phone, group)
- Add / Edit / Delete inline forms
- Import from CSV (same format as CLI app)
- Google Contacts sync button: triggers OAuth flow if not yet authorized, then pulls contacts from Google People API into local DB (merge by phone number — no duplicates)

### Templates
- List of saved templates with name and preview
- Create/edit template: name field + markdown editor (textarea with monospace font)
- Rendered preview panel alongside the editor
- Delete with confirmation
- Markdown rendered using `mistune` library

### History
- Chronological table of all sent messages
- Columns: date/time, recipients, message preview, status (sent/failed)
- Filterable by date range and status
- Click a row to expand and see full message text

### Settings
- Textbee API Key and Device ID fields (reads/writes `.env` file)
- Google Contacts: shows auth status, "Connect Google Account" button triggers OAuth flow, "Disconnect" revokes token
- "Test connection" button sends a test ping to Textbee API

---

### Help
A static in-app reference page accessible from the sidebar. Covers:

- **Getting Started** — prerequisites (Textbee account, Android app, API key), how to run the web app
- **Send a Message** — how to pick recipients, use templates, and send
- **Contacts** — how to add/edit/delete contacts, import from CSV, and sync with Google Contacts (including how to set up Google OAuth credentials)
- **Templates** — how to create and use markdown templates, markdown syntax reference
- **History** — how to read the message log, what status values mean
- **Settings** — where to find Textbee credentials, how to connect Google account
- **CLI App** — brief note that `sms.py` continues to work independently and shares the same contacts database

The Help page is rendered from a static Jinja2 template (no database access). It is always accessible regardless of whether credentials are configured.

---

## Google Contacts Integration

- Uses **Google People API** via `google-auth-oauthlib` + `google-api-python-client`
- OAuth 2.0 flow: user clicks "Connect" → redirected to Google consent screen → callback stores token in `.env` (or a local `token.json`)
- Sync logic: fetch all contacts with phone numbers from Google, insert/update local DB by matching on normalized phone number; if a match exists, update the name to the Google value; if no match, insert as new contact
- Sync is manual (button-triggered), not automatic
- Requires user to create a Google Cloud project and OAuth credentials (documented in README)

---

## Error Handling

- **Textbee API failure:** log error to `messages.error`, show failure status in history; do not retry automatically
- **Google OAuth failure:** show error message in Settings, keep existing contacts intact
- **DB errors:** surface as 500 error pages with a plain message
- All errors logged to console (stdout) for local debugging

---

## Dependencies

```
Flask>=3.0
google-auth-oauthlib>=1.2
google-api-python-client>=2.100
mistune>=3.0       # markdown rendering
python-dotenv>=1.0
```

---

## Running the App

```bash
pip install -r requirements.txt
python web_app/app.py
# Open http://localhost:5000
```

The CLI app (`sms.py`) continues to work independently by running `python sms.py` as before.

---

## Out of Scope

- Scheduled / recurring message sending (deferred for future version)
- User authentication (local only, no login needed)
- Mobile-responsive design (desktop browser only)
- Email notifications
- SMS replies / inbound messages
- Multi-user support

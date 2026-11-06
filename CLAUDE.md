# SMS App
Sends SMS through the Textbee API using your own Android phone as the gateway, from a command-line menu (`sms.py`) and a Flask web app (`web_app/`). Stack: Python 3.12 (CI also runs 3.10 to 3.13), Flask, SQLite (`contacts.db`), gunicorn in Docker.

## Commands
Secrets come from Doppler (`doppler.yaml`): run anything that needs them with `doppler run -- <command>`.
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- CLI app: `doppler run -- python3 sms.py`
- Dev server: `doppler run -- python3 -m web_app.app` (serves <http://127.0.0.1:5000>; `FLASK_DEBUG=1` for debug)
- Docker: `docker compose up --build` (serves <http://127.0.0.1:5050>)
- Test all / one: `pytest -q` / `pytest -q tests/test_db.py::test_name`
- Lint + format: none configured (`.claude/hooks/format.sh` does nothing until a ruff config exists)
- Typecheck: none configured

## Architecture
- `sms.py`: the interactive command-line app.
- `web_app/app.py`: Flask app factory (`create_app()`); blueprints live in `web_app/routes/` (auth, contacts, help, history, msg_templates, send, settings).
- `web_app/db.py`: SQLite access. `web_app/textbee.py`: Textbee API client. `web_app/google_sync.py`: Google contacts sync (OAuth).
- `tests/`: pytest, one file per module plus `tests/routes/`.

## Conventions and gotchas
- Credentials: `TEXTBEE_API_KEY`, `TEXTBEE_DEVICE_ID`, `FLASK_SECRET_KEY` and `GOOGLE_CLIENT_SECRET_FILE` (a path) come from the environment. Never print or commit them.
- Local-only files that stay git-ignored: `.env`, `contacts.db`, `token.json`, `client_secret*.json`.
- Phone numbers are standardised to `+1XXXXXXXXXX` before sending.
- The container runs as a non-root user with data in `/data` (`APP_DATA_DIR`).

## Don't touch
- `Guardians*` and `guardians_txt.csv` (personal data, ignored), `textbee.dev.*.apk`, `dist/`.

# Interactive SMS App

A lightweight, interactive command-line application that allows you to send SMS messages using the [Textbee](https://textbee.dev) API directly from your computer, using your own Android phone as the gateway.

## Features

- **Interactive Menu:** No need to memorize complicated command-line arguments. The app will guide you through prompts.
- **Contact Management (CRUD):** Manually create, read/list, update, and delete contacts, or import them in bulk from a CSV file. All contacts are stored securely in a local SQLite database (`contacts.db`).
- **Phone Number Standardization:** Automatic formatting of phone numbers (e.g., standardizing to `+1XXXXXXXXXX` for US numbers) to ensure seamless delivery via the Textbee gateway.
- **Send to Individuals or Groups:** Quickly look up a saved contact or group, or simply enter a phone number manually.
- **Markdown Support:** Draft your messages ahead of time in a markdown file (like `message.md`) and have the app read and send the contents automatically.

## Prerequisites

1. **Textbee Account:** Create a free account at [textbee.dev](https://textbee.dev).
2. **Textbee Android App:** Install the Textbee app on your Android phone and link it to your account (e.g., by scanning the QR code on your Textbee dashboard).
3. **Credentials:** You will need your **Device ID** and **API Key** from your Textbee dashboard.

## Setup

To avoid typing your credentials every time you run the app, you can create a `.env` file in the same directory as the script.

1. Open the `.env` file (or create one if it doesn't exist).
2. Add your credentials like so:

```ini
TEXTBEE_API_KEY=your_api_key_here
TEXTBEE_DEVICE_ID=your_device_id_here
```

*(If you choose not to use a `.env` file, the app will securely prompt you to enter them when you try to send a message).*

## Usage

Run the script using Python:

```bash
python3 sms.py
```

### Main Menu

When the app starts, you will see the following menu:

1. **Manage Contacts:** Opens a submenu to perform operations on your contacts:
   - **Add Contact (Create):** Manually add a contact by entering a name, phone number, and optional group name.
   - **List Contacts (Read):** Display all currently saved contacts in a structured table.
   - **Update Contact (Update):** Edit the Name, Phone, and/or Group of a contact selected by ID.
   - **Delete Contact (Delete):** Permanently remove a contact from the database by ID (requires confirmation).
2. **Import Contacts from CSV:** Provide the path to a `.csv` file to load contacts in bulk. The CSV must contain `Name` and `Phone` columns (an optional `Group` column is supported).
3. **Send Message:**
   - Choose a recipient (Individual from DB, Group from DB, or a manually entered number).
   - Choose your message source (Type it directly into the terminal, or provide the path to a Markdown file).
4. **Exit:** Close the application.

---

## Web App

A browser-based interface for the same SMS functionality, running locally alongside this CLI app.

### Setup

Requires **Python 3.10+** (the project venv is built on 3.14).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
source .venv/bin/activate
python -m web_app.app
```

Open **http://localhost:5000** in your browser.

By default the server runs with Flask's debugger and reloader **off**. To enable them during local development:

```bash
FLASK_DEBUG=1 python -m web_app.app
```

Do not set `FLASK_DEBUG=1` if the app is reachable from anything other than `localhost` — the Werkzeug debugger allows arbitrary code execution.

Both apps share `contacts.db` — contacts added in either app are visible in both.

### Google Contacts Setup

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. Click **Connect Google Account** to authorize

---

## Security Notes

- **Credentials live in `.env`**, which is excluded from git via `.gitignore` and permissioned `600` (owner-only read/write). Never commit it.
- **`FLASK_SECRET_KEY`** is generated automatically on first run and persisted to `.env`. Don't share this file — it signs session cookies and the Google OAuth `state` parameter.
- **No authentication** is implemented on any route. The app is intended for single-user local use, bound to `127.0.0.1` by default. If you ever need to expose it beyond your own machine, add an auth layer first.
- **Dependencies**: run `pip install pip-audit && pip-audit` periodically (or after updating `requirements.txt`) to check for newly disclosed CVEs in installed packages.

---

## Example CSV Format

If you are importing contacts, your CSV file should look like this:

```csv
Name,Phone,Group
Alice Smith,+15551234567,Friends
Bob Johnson,+15559876543,Friends
Charlie Brown,+15555555555,Family
```

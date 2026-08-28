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

`contacts.db` is created automatically on first run with the correct schema — no manual setup or seed file needed. It's excluded from git (see `.gitignore`), so each clone starts with an empty database.

By default the server runs with Flask's debugger and reloader **off**. To enable them during local development:

```bash
FLASK_DEBUG=1 python -m web_app.app
```

Do not set `FLASK_DEBUG=1` if the app is reachable from anything other than `localhost` — the Werkzeug debugger allows arbitrary code execution.

Both apps share `contacts.db` — contacts added in either app are visible in both.

### Running in Docker (e.g. Synology DiskStation)

The web app ships with a `Dockerfile` and `docker-compose.yml`. The container reads/writes `.env`, `contacts.db`, and `token.json` in a single `/data` volume (set via the `APP_DATA_DIR` env var), so all state survives container rebuilds. `/data` is a **named Docker volume** (`sms-app-data`), not a bind-mounted folder — this matters on Synology, see below.

**Build and run locally:**

```bash
docker compose up -d --build
```

Open **http://localhost:5050**. Docker creates the `sms-app-data` named volume automatically on first run — that's where `.env`, `contacts.db`, and `token.json` live.

**On Synology DiskStation (DSM 7.2+, Container Manager):**

Use the **Project** feature (Compose-based), not the plain **Container → Create** wizard — the wizard only supports folder/file bind mounts, not named volumes, and this app's non-root container needs a named volume to avoid a Synology-specific ACL permission problem (see the gotcha below).

1. Copy the project folder to the NAS (e.g. via File Station or `git clone` through SSH) — you don't need `.venv`, it's excluded from the image.
2. Open **Container Manager** → **Project** → **Create**.
3. Set the project path to the folder containing `docker-compose.yml`, and let it build from the Dockerfile.
4. Start the project. The app listens on host port `5050` by default (mapped to `5000` in the container) — **DSM's own web admin interface (nginx) uses port 5000**, so this app avoids that conflict out of the box. Adjust the `ports:` mapping in `docker-compose.yml` if `5050` is also taken.
5. Set TextBee credentials and Google OAuth in the **Settings** page as usual — they're saved into the `sms-app-data` volume on the NAS.

**If you already have a container running from the older bind-mount setup** (or created one via the Container wizard instead of a Project), recreate it via SSH instead so it gets a proper named volume:

```bash
sudo /var/packages/ContainerManager/target/usr/bin/docker rm -f sms-app
sudo /var/packages/ContainerManager/target/usr/bin/docker volume create sms-app-data
sudo /var/packages/ContainerManager/target/usr/bin/docker run -d --name sms-app --restart unless-stopped -p 5050:5000 -v sms-app-data:/data sms-app:synology
```

(Path to the `docker` binary and the exact image tag may differ depending on how you built/imported it — check with `sudo /var/packages/ContainerManager/target/usr/bin/docker images`.)

**Synology gotcha — ACLs vs. non-root containers:** this container runs as a non-root user (uid 1000) for security. If you bind-mount a regular Synology shared folder to `/data` instead of using a named volume, DSM's Btrfs ACL system silently overrides plain POSIX permissions (`chmod 777` included) — uid 1000 isn't a real DSM user, so it falls into the restrictive `everyone: read-only` ACL bucket and the app fails to boot with `PermissionError: [Errno 13] Permission denied: '/data/.env'`. A named Docker volume sidesteps DSM's ACL system entirely and just works — this is also how the container's `Dockerfile` already sets correct ownership on the `/data` directory before switching to the non-root user, so a fresh named volume inherits the right permissions automatically.

For the Google OAuth credentials JSON file: since the container can't see paths on your Mac, place the downloaded credentials file inside the data volume (e.g. `docker cp client_secret.json sms-app:/data/`) and enter `/data/client_secret.json` as the path in Settings.

**Security note:** this app has no login/authentication (see Security Notes below). If the NAS is reachable beyond your LAN, restrict access at the DSM firewall or reverse proxy layer before exposing the app's port.

### Google Contacts Setup

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. Click **Connect Google Account** to authorize

---

## Security Notes

- **Credentials live in `.env`**, which is excluded from git via `.gitignore` and permissioned `600` (owner-only read/write) — enforced on every write, not just at creation. Never commit it.
- **`FLASK_SECRET_KEY`** is generated automatically on first run and persisted to `.env`. Don't share this file — it signs session cookies and the Google OAuth `state` parameter, which is now validated on callback to prevent login-CSRF.
- **CSRF protection** (Flask-WTF) is enabled on all state-changing routes. All forms carry a token; the two routes that used to be CSRF-able `GET` links (Google contacts sync, Google disconnect) are now `POST`-only.
- **No authentication** is implemented on any route. The app is intended for single-user local use, bound to `127.0.0.1` by default. If you ever need to expose it beyond your own machine, add an auth layer first. This matters more once containerized — see the Docker section above about binding to `127.0.0.1` on the host.
- **Docker**: the container runs as a non-root user (`app`, uid 1000), not root. Use the named Docker volume (`sms-app-data`) declared in `docker-compose.yml` for `/data`, not a bind-mounted host folder — on Synology specifically, DSM's ACL system overrides POSIX permissions on bind-mounted shared folders and will silently deny uid 1000 write access even at `chmod 777`. See the Synology section above for details and the fix if you hit this.
- **Dependencies**: run `pip install pip-audit && pip-audit` periodically (or after updating `requirements.txt`) to check for newly disclosed CVEs in installed packages.
- **Secret scanning**: GitHub secret scanning + push protection are enabled on this repo, and a local [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook blocks commits containing recognizable secret patterns. To set up the local hook after cloning:

  ```bash
  brew install gitleaks pre-commit
  pre-commit install
  ```

---

## Example CSV Format

If you are importing contacts, your CSV file should look like this:

```csv
Name,Phone,Group
Alice Smith,+15551234567,Friends
Bob Johnson,+15559876543,Friends
Charlie Brown,+15555555555,Family
```

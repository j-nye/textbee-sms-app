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

**Using a prebuilt image instead of building on the NAS:** if you build and push the image to a registry (e.g. a **private** Docker Hub repo), a Project can pull it instead of building. Build for the NAS's CPU (`linux/amd64` for most Synology models, `linux/arm64` for some; use both to be safe):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <your-dockerhub-user>/sms-app:latest --push .
```

The image holds code only — `.dockerignore` keeps `.env`, `*.db`, `*.csv`, and `token.json` out, and runtime data lives in the `sms-app-data` volume, never in the image. Then use this Project compose file (log the NAS in to Docker Hub first under Container Manager → Registry → Settings if the repo is private):

```yaml
services:
  sms-app:
    image: <your-dockerhub-user>/sms-app:latest
    container_name: sms-app
    restart: unless-stopped
    mem_limit: 512m
    ports:
      - "5050:5000"
    volumes:
      - sms-app-data:/data

volumes:
  sms-app-data:
    name: sms-app-data
```

`name: sms-app-data` pins the volume name so it is the same regardless of the project name. About 512 MB of memory is a comfortable limit; the app typically uses far less.

**Updating to a new version:** your data stays in the `sms-app-data` volume, so updating only replaces the code.

- Built on the NAS from source: update the project folder (`git pull`), then in Container Manager choose Project → *Action* → *Build*, or over SSH run `sudo docker compose up -d --build`.
- Prebuilt image: `sudo docker compose pull && sudo docker compose up -d`.

**Never delete the `sms-app-data` volume.** Deleting a *container* is safe; the volume survives it. But `docker compose down -v`, `docker volume rm sms-app-data`, or choosing to delete volumes when removing a Project destroys your database and settings permanently.

**Backup and restore:** all state lives in the volume (on a Synology it is under `/volume1/@docker/volumes/sms-app-data/_data/`, which File Station and Hyper Backup don't see by default). Make a tarball in a normal shared folder, then copy it off the NAS or include that folder in a Hyper Backup task. The archive contains your TextBee API key, so keep it private.

```bash
sudo mkdir -p /volume1/docker/backups
sudo docker run --rm -v sms-app-data:/data -v /volume1/docker/backups:/backup alpine \
  tar czf /backup/sms-app-data-$(date +%F).tar.gz -C /data .
```

To restore, stop the project and extract into the volume, restoring ownership for the app's non-root user (uid 1000):

```bash
sudo docker run --rm -v sms-app-data:/data -v /volume1/docker/backups:/backup alpine \
  sh -c "cd /data && tar xzf /backup/sms-app-data-YYYY-MM-DD.tar.gz && chown -R 1000:1000 /data"
```

**Security note:** the app requires a login (see Security Notes below), but a plain `5050:5000` mapping serves it over unencrypted HTTP on your LAN, so your password and session cookie travel in the clear. For anything beyond a trusted home network, put it behind a TLS reverse proxy (DSM: Control Panel → Login Portal → Advanced → Reverse Proxy) and bind the port to `127.0.0.1:5050:5000` as the repo's `docker-compose.yml` does, restricting access at the DSM firewall as needed.

### Google Contacts Setup

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **People API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON file
5. In the web app, go to **Settings** and set the path to that file in "Google OAuth Credentials File"
6. In the same page, set **Public Base URL** to the URL you use to reach this app (e.g. `http://192.168.1.50:5050` for LAN use, or `https://sms.example.com` behind a reverse proxy) — this is used to build the OAuth redirect link instead of trusting the request's `Host` header
7. Click **Connect Google Account** to authorize

### Changing Your Password

Sign in and go to **🔑 Password** in the sidebar. You'll need your current password plus a new one (minimum 10 characters) — this is the normal way to change it while you're logged in.

### Password Recovery

The web app requires signing in, and there's no email-based password reset for when you're locked out — if you forget your password, delete the `users` row from the database and restart. The app will show the first-run **/setup** screen again; your contacts, templates, and message history are untouched.

**Docker:**

```bash
docker compose cp sms-app:/data/contacts.db ./contacts.db.bak   # back up first
docker compose exec sms-app python -c "import sqlite3;c=sqlite3.connect('/data/contacts.db');c.execute('DELETE FROM users');c.commit()"
docker compose restart sms-app
```

**Local / non-Docker:**

```bash
sqlite3 contacts.db "DELETE FROM users;"
```

Then restart the app.

If the app is fronted by a TLS reverse proxy, set `SESSION_COOKIE_SECURE=true` in `.env` so session cookies are only sent over HTTPS. Leave it unset (or `false`) for plain-HTTP local/LAN use — setting it to `true` without TLS in front will make login silently fail, since browsers won't send a `Secure` cookie back over HTTP.

---

## Security Notes

- **Credentials live in `.env`**, which is excluded from git via `.gitignore` and permissioned `600` (owner-only read/write) — enforced on every write, not just at creation. Never commit it.
- **`FLASK_SECRET_KEY`** is generated automatically on first run and persisted to `.env`. Don't share this file — it signs session cookies and the Google OAuth `state` parameter, which is now validated on callback to prevent login-CSRF.
- **CSRF protection** (Flask-WTF) is enabled on all state-changing routes. All forms carry a token; the two routes that used to be CSRF-able `GET` links (Google contacts sync, Google disconnect) are now `POST`-only.
- **Login is required** for every route except the one-time first-run setup screen. The app is intended for single-user local use, bound to `127.0.0.1` by default — see the Docker section above about binding to `127.0.0.1` on the host, and the Password Recovery section above if you forget your password.
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

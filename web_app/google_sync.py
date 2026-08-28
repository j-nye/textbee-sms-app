from __future__ import annotations
import os
from .textbee import normalize_phone

SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']
DATA_DIR = os.environ.get('APP_DATA_DIR', os.path.dirname(os.path.dirname(__file__)))
TOKEN_FILE = os.path.join(DATA_DIR, 'token.json')


def is_connected() -> bool:
    return os.path.exists(TOKEN_FILE)


def disconnect() -> None:
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def get_credentials():
    """Load credentials from token.json. Returns None if not connected."""
    from google.oauth2.credentials import Credentials
    if not os.path.exists(TOKEN_FILE):
        return None
    return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)


def start_oauth_flow(client_secret_file: str, redirect_uri: str):
    """Start OAuth flow. Returns (auth_url, state, flow)."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file, SCOPES, redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true'
    )
    return auth_url, state, flow


def fetch_google_contacts(creds) -> list[dict]:
    """Fetch all contacts with phone numbers from Google People API."""
    from googleapiclient.discovery import build
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


def extract_contacts(people: list[dict]) -> list[tuple[str, str]]:
    """Extract (name, phone) tuples from Google People API response."""
    contacts = []
    for person in people:
        names = person.get('names', [])
        phones = person.get('phoneNumbers', [])
        if not names or not phones:
            continue
        name = names[0].get('displayName', '').strip()
        phone = normalize_phone(phones[0].get('value', '').strip())
        if name and phone:
            contacts.append((name, phone))
    return contacts


def merge_contacts(db, contacts: list[tuple[str, str]]) -> int:
    """
    Upsert contacts into the DB by phone number.
    Updates name if phone exists; inserts if new.
    Returns count of inserted rows.
    """
    inserted = 0
    for name, phone in contacts:
        existing = db.execute(
            'SELECT id FROM contacts WHERE phone=?', (phone,)
        ).fetchone()
        if existing:
            db.execute('UPDATE contacts SET name=? WHERE phone=?', (name, phone))
        else:
            db.execute(
                'INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, NULL)',
                (name, phone)
            )
            inserted += 1
    db.commit()
    return inserted


def sync_google_contacts(db) -> tuple[bool, str]:
    """
    Full sync: load credentials, fetch contacts, merge into DB.
    Returns (success, message).
    """
    creds = get_credentials()
    if not creds:
        return False, 'Google account not connected.'
    try:
        people = fetch_google_contacts(creds)
        contacts = extract_contacts(people)
        count = merge_contacts(db, contacts)
        return True, f'Synced {len(contacts)} contacts ({count} new).'
    except Exception as e:
        return False, f'Sync failed: {e}'

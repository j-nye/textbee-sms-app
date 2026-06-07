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

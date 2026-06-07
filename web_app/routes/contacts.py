import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
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
    flash('Contact added.', 'success')
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
        flash('Contact deleted.', 'success')
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

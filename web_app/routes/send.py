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

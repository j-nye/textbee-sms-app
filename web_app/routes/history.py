import json
from flask import Blueprint, render_template, request
from ..db import get_db

bp = Blueprint('history', __name__, url_prefix='/history')


@bp.route('/')
def index():
    db = get_db()
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = 'SELECT id, recipients, message, sent_at, status, error FROM messages'
    params = []
    conditions = []

    if status_filter in ('sent', 'failed'):
        conditions.append('status = ?')
        params.append(status_filter)
    if date_from:
        conditions.append('sent_at >= ?')
        params.append(date_from)
    if date_to:
        conditions.append('sent_at <= ?')
        params.append(date_to + 'T23:59:59')

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY sent_at DESC'

    rows = db.execute(query, params).fetchall()

    messages = []
    for row in rows:
        recipients = json.loads(row['recipients'])
        messages.append({
            'id': row['id'],
            'recipients': recipients,
            'recipient_display': ', '.join(recipients[:3]) + (f' +{len(recipients)-3} more' if len(recipients) > 3 else ''),
            'message': row['message'],
            'message_preview': row['message'][:80] + ('…' if len(row['message']) > 80 else ''),
            'sent_at': row['sent_at'],
            'status': row['status'],
            'error': row['error'],
        })

    return render_template('history.html', messages=messages,
                           status_filter=status_filter,
                           date_from=date_from, date_to=date_to)

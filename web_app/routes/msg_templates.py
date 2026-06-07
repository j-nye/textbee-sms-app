from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
import mistune
from ..db import get_db

bp = Blueprint('msg_templates', __name__, url_prefix='/templates')
_markdown = mistune.create_markdown()


@bp.route('/')
def index():
    db = get_db()
    templates = db.execute(
        'SELECT id, name, body_markdown, updated_at FROM msg_templates ORDER BY name'
    ).fetchall()
    return render_template('msg_templates.html', templates=templates, markdown=_markdown)


@bp.route('/create', methods=['POST'])
def create():
    name = request.form.get('name', '').strip()
    body = request.form.get('body_markdown', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('msg_templates.index'))

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        'INSERT INTO msg_templates (name, body_markdown, created_at, updated_at) VALUES (?, ?, ?, ?)',
        (name, body, now, now)
    )
    db.commit()
    flash(f'Template "{name}" saved.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/edit/<int:tmpl_id>', methods=['POST'])
def edit(tmpl_id):
    name = request.form.get('name', '').strip()
    body = request.form.get('body_markdown', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('msg_templates.index'))

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        'UPDATE msg_templates SET name=?, body_markdown=?, updated_at=? WHERE id=?',
        (name, body, now, tmpl_id)
    )
    db.commit()
    flash('Template updated.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/delete/<int:tmpl_id>', methods=['POST'])
def delete(tmpl_id):
    db = get_db()
    row = db.execute('SELECT name FROM msg_templates WHERE id=?', (tmpl_id,)).fetchone()
    if row:
        db.execute('DELETE FROM msg_templates WHERE id=?', (tmpl_id,))
        db.commit()
        flash('Template deleted.', 'success')
    return redirect(url_for('msg_templates.index'))


@bp.route('/preview/<int:tmpl_id>')
def preview(tmpl_id):
    db = get_db()
    row = db.execute('SELECT body_markdown FROM msg_templates WHERE id=?', (tmpl_id,)).fetchone()
    if not row:
        return '', 404
    return _markdown(row['body_markdown'])

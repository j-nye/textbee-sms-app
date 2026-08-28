from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from ..db import get_db, user_exists

bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 10
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_BASE_SECONDS = 30
LOCKOUT_MAX_SECONDS = 15 * 60
GENERIC_LOGIN_ERROR = 'Invalid username or password.'

# Fixed dummy hash checked when a username doesn't exist, so login takes the
# same code path either way and doesn't leak which usernames are registered.
_DUMMY_HASH = generate_password_hash('a-password-that-is-never-valid')


def _validate_new_password(password, confirm):
    if password != confirm:
        return 'Passwords do not match.'
    if len(password) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    return None


def _start_session(user_id, username):
    session.clear()
    session['user_id'] = user_id
    session['username'] = username
    session.permanent = True


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if user_exists():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username:
            flash('Username is required.', 'error')
            return redirect(url_for('auth.setup'))

        error = _validate_new_password(password, confirm)
        if error:
            flash(error, 'error')
            return redirect(url_for('auth.setup'))

        now = datetime.now(timezone.utc).isoformat()
        db = get_db()
        cur = db.execute(
            'INSERT INTO users (username, password_hash, created_at, password_changed_at, failed_attempts) '
            'SELECT ?, ?, ?, ?, 0 WHERE NOT EXISTS (SELECT 1 FROM users)',
            (username, generate_password_hash(password), now, now),
        )
        db.commit()
        if cur.rowcount == 0:
            flash('An account already exists. Please log in.', 'info')
            return redirect(url_for('auth.login'))

        _start_session(cur.lastrowid, username)
        flash('Account created. Welcome!', 'success')
        return redirect(url_for('send.index'))

    return render_template('setup.html', min_length=MIN_PASSWORD_LENGTH)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if not user_exists():
        return redirect(url_for('auth.setup'))
    if session.get('user_id'):
        return redirect(url_for('send.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        row = db.execute(
            'SELECT id, username, password_hash, failed_attempts, locked_until FROM users WHERE username = ?',
            (username,),
        ).fetchone()

        now = datetime.now(timezone.utc)
        if row and row['locked_until'] and datetime.fromisoformat(row['locked_until']) > now:
            # Deliberately the same generic message as any other failure, so a
            # locked-out username can't be distinguished from an unknown one.
            flash(GENERIC_LOGIN_ERROR, 'error')
            return redirect(url_for('auth.login'))

        stored_hash = row['password_hash'] if row else _DUMMY_HASH
        password_ok = check_password_hash(stored_hash, password) and row is not None

        if not password_ok:
            if row:
                # Atomic increment first, so concurrent failed attempts can't
                # race each other into a lost update on failed_attempts.
                db.execute('UPDATE users SET failed_attempts = failed_attempts + 1 WHERE id = ?', (row['id'],))
                db.commit()
                failed_attempts = db.execute(
                    'SELECT failed_attempts FROM users WHERE id = ?', (row['id'],)
                ).fetchone()['failed_attempts']
                if failed_attempts >= MAX_FAILED_ATTEMPTS:
                    delay = min(
                        LOCKOUT_BASE_SECONDS * 2 ** (failed_attempts - MAX_FAILED_ATTEMPTS),
                        LOCKOUT_MAX_SECONDS,
                    )
                    locked_until = (now + timedelta(seconds=delay)).isoformat()
                    db.execute('UPDATE users SET locked_until = ? WHERE id = ?', (locked_until, row['id']))
                    db.commit()
                    current_app.logger.warning(
                        'account locked after %d failed attempts (user_id=%s) until %s',
                        failed_attempts, row['id'], locked_until,
                    )
            flash(GENERIC_LOGIN_ERROR, 'error')
            return redirect(url_for('auth.login'))

        db.execute(
            'UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?',
            (row['id'],),
        )
        db.commit()

        _start_session(row['id'], row['username'])
        return redirect(url_for('send.index'))

    return render_template('login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Signed out.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    # 'auth.change_password' is not in the gate's public-endpoint allowlist,
    # so the before_request gate in app.py already enforces login here.
    if request.method == 'POST':
        db = get_db()
        row = db.execute('SELECT id, password_hash FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not row:
            session.clear()
            flash('Your account no longer exists. Please set up again.', 'error')
            return redirect(url_for('auth.setup'))

        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not check_password_hash(row['password_hash'], current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('auth.change_password'))

        error = _validate_new_password(new_password, confirm_password)
        if error:
            flash(error, 'error')
            return redirect(url_for('auth.change_password'))

        if check_password_hash(row['password_hash'], new_password):
            flash('New password must be different from your current password.', 'error')
            return redirect(url_for('auth.change_password'))

        db.execute(
            'UPDATE users SET password_hash = ?, password_changed_at = ?, '
            'failed_attempts = 0, locked_until = NULL WHERE id = ?',
            (generate_password_hash(new_password), datetime.now(timezone.utc).isoformat(), row['id']),
        )
        db.commit()
        current_app.logger.info('password changed (user_id=%s)', row['id'])

        _start_session(row['id'], session.get('username'))
        flash('Password changed.', 'success')
        return redirect(url_for('auth.change_password'))

    return render_template('change_password.html', min_length=MIN_PASSWORD_LENGTH)

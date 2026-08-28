import os
import secrets
from flask import Flask, redirect, url_for
from flask_wtf import CSRFProtect
from . import db as database


def _load_or_create_secret_key(env_file: str | None) -> str:
    """Read FLASK_SECRET_KEY from .env, generating and persisting one if absent."""
    if not env_file:
        return secrets.token_hex(32)

    lines = []
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('FLASK_SECRET_KEY='):
                value = line.split('=', 1)[1].strip().strip('"\'')
                if value:
                    return value

    key = secrets.token_hex(32)
    with open(env_file, 'a') as f:
        if lines and not lines[-1].endswith('\n'):
            f.write('\n')
        f.write(f'FLASK_SECRET_KEY={key}\n')
    os.chmod(env_file, 0o600)
    return key


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)

    data_dir = os.environ.get('APP_DATA_DIR', os.path.dirname(os.path.dirname(__file__)))
    env_file = os.path.join(data_dir, '.env')
    app.config.from_mapping(
        DATABASE=os.path.join(data_dir, 'contacts.db'),
        ENV_FILE=env_file,
        SESSION_COOKIE_SAMESITE='Strict',
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )

    if test_config is not None:
        app.config.update(test_config)

    app.config.setdefault('SECRET_KEY', None)
    if not app.config['SECRET_KEY']:
        app.config['SECRET_KEY'] = _load_or_create_secret_key(app.config.get('ENV_FILE'))

    CSRFProtect(app)
    database.init_app(app)
    with app.app_context():
        database.init_db()

    from .routes import help, send, contacts, msg_templates, history, settings
    app.register_blueprint(help.bp)
    app.register_blueprint(send.bp)
    app.register_blueprint(contacts.bp)
    app.register_blueprint(msg_templates.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(settings.bp)

    @app.route('/')
    def index():
        return redirect(url_for('send.index'))

    return app


if __name__ == '__main__':
    app = create_app()
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host=os.environ.get('FLASK_HOST', '127.0.0.1'), port=5000)

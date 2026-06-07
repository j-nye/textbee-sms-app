import os
from flask import Flask
from . import db as database


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)

    app.config.from_mapping(
        SECRET_KEY='dev-change-in-production',
        DATABASE=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'contacts.db'),
        ENV_FILE=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
    )

    if test_config is not None:
        app.config.update(test_config)

    database.init_app(app)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        database.init_db()
    app.run(debug=True, port=5000)

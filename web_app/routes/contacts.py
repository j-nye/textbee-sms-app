from flask import Blueprint, render_template
bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@bp.route('/')
def index():
    return render_template('contacts.html')

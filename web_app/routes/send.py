from flask import Blueprint, render_template
bp = Blueprint('send', __name__, url_prefix='/send')

@bp.route('/')
def index():
    return render_template('send.html')

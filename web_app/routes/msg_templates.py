from flask import Blueprint, render_template
bp = Blueprint('msg_templates', __name__, url_prefix='/templates')

@bp.route('/')
def index():
    return render_template('msg_templates.html')

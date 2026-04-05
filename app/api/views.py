from flask import Blueprint, render_template

bp = Blueprint('views', __name__)


@bp.route('/')
def index():
    return render_template('login.html')


@bp.route('/login')
def login():
    return render_template('login.html')


@bp.route('/register')
def register():
    return render_template('register.html')


@bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@bp.route('/products')
def products():
    return render_template('products.html')


@bp.route('/alerts')
def alerts():
    return render_template('alerts.html')

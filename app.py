import os
import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ----------------------- التهيئة الأساسية -----------------------
app = Flask(__name__)
# استخدام مفتاح سري متغير لزيادة الأمان
app.secret_key = os.environ.get('SECRET_KEY', '7a8b3c9d1e2f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b')

# ملاحظة: للاستخدام على Vercel يفضل استخدام قاعدة بيانات خارجية (PostgreSQL مثلاً)
# إذا كنت تستخدم SQLite محلياً، تأكد من المسار الصحيح
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'security_tax.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# رقم هاتف المتحكم
CONTROLLER_PHONE = "967770295876"

# ----------------------- نماذج قاعدة البيانات -----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # admin, viewer, collector
    full_name = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Governorate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    districts = db.relationship('District', backref='governorate', lazy=True, cascade='all, delete-orphan')

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    governorate_id = db.Column(db.Integer, db.ForeignKey('governorate.id'), nullable=False)
    markets = db.relationship('Market', backref='district', lazy=True, cascade='all, delete-orphan')
    atms = db.relationship('ATM', backref='district', lazy=True, cascade='all, delete-orphan')

class Market(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    shops = db.relationship('Shop', backref='market', lazy=True, cascade='all, delete-orphan')

class ATM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100))
    tax_number = db.Column(db.String(50), unique=True)
    market_id = db.Column(db.Integer, db.ForeignKey('market.id'), nullable=False)
    tax_payments = db.relationship('TaxPayment', backref='shop', lazy=True)

class TaxPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    receipt_no = db.Column(db.String(50), unique=True)
    notes = db.Column(db.String(200))

class CampaignTax(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_name = db.Column(db.String(100), nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    collected_amount = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')

# ----------------------- دوال مساعدة -----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('غير مصرح به، يلزم صلاحية مدير', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', full_name='مدير النظام')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    if Governorate.query.count() == 0:
        govs = ['عدن', 'حضرموت', 'الضالع', 'ابين', 'لحج', 'يافع', 'شبوه']
        for g in govs:
            db.session.add(Governorate(name=g))
        db.session.commit()

# ----------------------- واجهات HTML -----------------------
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>النظام الأمني والضريبي المتكامل</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body { background: #f0f2f5; font-family: 'Tahoma', sans-serif; }
        .navbar { box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .sidebar { min-height: 100vh; background: #2c3e50; color: white; }
        .sidebar a { color: #ecf0f1; text-decoration: none; display: block; padding: 10px 15px; }
        .sidebar a:hover { background: #1abc9c; }
        .content { padding: 20px; }
        .footer { text-align: center; margin-top: 30px; padding: 15px; background: #2c3e50; color: white; }
        .phone-badge { background: #e67e22; padding: 5px 10px; border-radius: 20px; font-size: 14px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/"><i class="fas fa-shield-alt"></i> النظام الأمني والضريبي</a>
            <div class="d-flex">
                {% if current_user.is_authenticated %}
                <span class="navbar-text mx-3"><i class="fas fa-user"></i> {{ current_user.full_name }}</span>
                <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">خروج</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <div class="container-fluid">
        <div class="row">
            {% if current_user.is_authenticated %}
            <div class="col-md-2 sidebar p-0">
                <div class="p-3">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-tachometer-alt"></i> لوحة التحكم</a>
                    <a href="{{ url_for('governorates') }}"><i class="fas fa-city"></i> المحافظات</a>
                    <a href="{{ url_for('districts') }}"><i class="fas fa-map-marker-alt"></i> المديريات</a>
                    <a href="{{ url_for('markets') }}"><i class="fas fa-store"></i> الأسواق</a>
                    <a href="{{ url_for('atms') }}"><i class="fas fa-money-bill-wave"></i> الصرافات</a>
                    <a href="{{ url_for('shops') }}"><i class="fas fa-shop"></i> المحلات</a>
                    <a href="{{ url_for('tax_payments') }}"><i class="fas fa-file-invoice-dollar"></i> سجل الضرائب</a>
                </div>
            </div>
            {% endif %}
            <div class="col-md-{{ '10' if current_user.is_authenticated else '12' }} content">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endwith %}
                {% block content %}{% endblock %}
            </div>
        </div>
    </div>
    <div class="footer">
        رقم هاتف المتحكم: <span class="phone-badge">{{ controller_phone }}</span>
    </div>
</body>
</html>
'''

# ----------------------- المسارات -----------------------
@app.context_processor
def inject_phone():
    return dict(controller_phone=CONTROLLER_PHONE)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('خطأ في البيانات', 'danger')
    return render_template_string('''
        {% extends "BASE" %}
        {% block content %}
        <div class="row justify-content-center mt-5">
            <div class="col-md-4 card p-4 shadow">
                <h4 class="text-center">تسجيل الدخول</h4>
                <form method="post">
                    <input type="text" name="username" class="form-control mb-3" placeholder="اسم المستخدم" required>
                    <input type="password" name="password" class="form-control mb-3" placeholder="كلمة المرور" required>
                    <button class="btn btn-primary w-100">دخول</button>
                </form>
            </div>
        </div>
        {% endblock %}
    ''', BASE=BASE_TEMPLATE)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_shops = Shop.query.count()
    total_tax = db.session.query(db.func.sum(TaxPayment.amount)).scalar() or 0
    return render_template_string('''
        {% extends "BASE" %}
        {% block content %}
        <h3>لوحة التحكم</h3>
        <div class="row">
            <div class="col-md-4 alert alert-info">إجمالي المحلات: {{ total_shops }}</div>
            <div class="col-md-4 alert alert-success">إجمالي الضرائب: {{ total_tax }} ريال</div>
        </div>
        {% endblock %}
    ''', BASE=BASE_TEMPLATE, total_shops=total_shops, total_tax=total_tax)

# مسارات المحافظات
@app.route('/governorates')
@login_required
def governorates():
    govs = Governorate.query.all()
    return render_template_string('''
        {% extends "BASE" %}
        {% block content %}
        <h3>المحافظات</h3>
        <table class="table">
            {% for g in govs %}
            <tr><td>{{ g.name }}</td></tr>
            {% endfor %}
        </table>
        {% endblock %}
    ''', BASE=BASE_TEMPLATE, govs=govs)

# (بقية المسارات: districts, markets, shops, tax_payments تتبع نفس النمط السابق)
# اختصاراً سيتم تفعيل تشغيل التطبيق

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=False)

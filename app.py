import os
import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ----------------------- التهيئة الأساسية -----------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', '7a8b3c9d1e2f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b')

# تعديل المسار ليعمل على Vercel بدون أخطاء الصلاحيات
if os.environ.get('VERCEL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/security_tax.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security_tax.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

CONTROLLER_PHONE = "967770295876"

# ----------------------- نماذج قاعدة البيانات -----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='viewer')
    full_name = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Governorate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    districts = db.relationship('District', backref='governorate', lazy=True)

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    governorate_id = db.Column(db.Integer, db.ForeignKey('governorate.id'), nullable=False)
    shops = db.relationship('Shop', backref='district', lazy=True)

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100))
    tax_number = db.Column(db.String(50), unique=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    tax_payments = db.relationship('TaxPayment', backref='shop', lazy=True)

class TaxPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

# ----------------------- القوالب والواجهات -----------------------
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>النظام الأمني والضريبي</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Arial', sans-serif; }
        .navbar { margin-bottom: 20px; }
        .footer { text-align: center; padding: 20px; color: #666; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">نظام الرقابة المتكامل</a>
            {% if current_user.is_authenticated %}
            <a href="/logout" class="btn btn-outline-light btn-sm">تسجيل خروج</a>
            {% endif %}
        </div>
    </nav>
    <div class="container">
        {% with messages = get_flashed_messages() %}
          {% if messages %}{% for msg in messages %}<div class="alert alert-info">{{ msg }}</div>{% endfor %}{% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <div class="footer">للدعم الفني اتصل بـ: {{ phone }}</div>
</body>
</html>
'''

# ----------------------- المسارات (Routes) -----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def dashboard():
    shops = Shop.query.all()
    return render_template_string('''
        {% extends "base" %}
        {% block content %}
        <h2>لوحة التحكم</h2>
        <div class="row mt-4">
            <div class="col-md-4"><div class="card p-3 shadow-sm">إجمالي المحلات: {{ shops|length }}</div></div>
        </div>
        {% endblock %}
    ''', base=BASE_TEMPLATE, shops=shops, phone=CONTROLLER_PHONE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة')
    return render_template_string('''
        {% extends "base" %}
        {% block content %}
        <div class="row justify-content-center">
            <div class="col-md-4">
                <form method="post" class="card p-4 shadow">
                    <h3 class="text-center mb-3">دخول</h3>
                    <input type="text" name="username" class="form-control mb-2" placeholder="اسم المستخدم" required>
                    <input type="password" name="password" class="form-control mb-3" placeholder="كلمة المرور" required>
                    <button class="btn btn-primary w-100">دخول</button>
                </form>
            </div>
        </div>
        {% endblock %}
    ''', base=BASE_TEMPLATE, phone=CONTROLLER_PHONE)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# ----------------------- تشغيل التطبيق -----------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # إضافة مستخدم أدمن افتراضي إذا لم يوجد
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', full_name='المدير العام', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)

import os
import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ----------------------- التهيئة الأساسية -----------------------
app = Flask(__name__)
# استخدام مفتاح سري من البيئة أو مفتاح افتراضي
app.secret_key = os.environ.get('SECRET_KEY', '7a8b3c9d1e2f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b')

# تعديل هام لـ Vercel: استخدام مسار مؤقت للقراءة فقط إذا لم تتوفر قاعدة بيانات خارجية
if os.environ.get('VERCEL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/security_tax.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security_tax.db'

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
    role = db.Column(db.String(20), default='viewer')
    full_name = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# (بقية النماذج: Governorate, District, Market, ATM, Shop, TaxPayment كما هي في ملفك)
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

# ----------------------- دوال التهيئة -----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', full_name='مدير النظام')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

# ----------------------- المسارات الأساسية -----------------------
@app.context_processor
def inject_phone():
    return dict(controller_phone=CONTROLLER_PHONE)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

# (أضف بقية المسارات من ملفك الأصلي هنا بنفس الترتيب)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=False)

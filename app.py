"""
المركز السيادي - ديوان محافظة عدن
نظام متكامل لإدارة الإيرادات والرقابة الميدانية

لتشغيل المشروع:
uvicorn main:app --reload --host 0.0.0.0 --port 8080
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import enum

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Enum, DateTime, ForeignKey, Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

# ============================================================
# الإعدادات
# ============================================================
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "ديوان محافظة عدن - المركز السيادي"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aden-sovereign-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sovereign_center.db")
    SOVEREIGN_MOBILE: str = "967770295876"
    class Config:
        case_sensitive = True

settings = Settings()

# ============================================================
# قاعدة البيانات
# ============================================================
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# النماذج
# ============================================================
class UserRole(str, enum.Enum):
    GOVERNOR = "governor"
    DISTRICT_MAYOR = "district_mayor"
    COLLECTOR = "collector"

class ShopCategory(str, enum.Enum):
    A = "أ - ممتاز"
    B = "ب - متوسط"
    C = "ج - صغير"

class ShopStatus(str, enum.Enum):
    ACTIVE = "نشط"
    INACTIVE = "غير نشط"
    BLOCKED = "محظور"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.COLLECTOR)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class District(Base):
    __tablename__ = "districts"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    mayor_name = Column(String(100))
    mayor_phone = Column(String(20))
    geo_fence_data = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    shops = relationship("Shop", back_populates="district")

class Shop(Base):
    __tablename__ = "shops"
    id = Column(Integer, primary_key=True, index=True)
    unique_code = Column(String(20), unique=True, index=True, nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    commercial_name = Column(String(200), nullable=False)
    activity_type = Column(String(100), nullable=False)
    commercial_register = Column(String(50))
    owner_name = Column(String(100), nullable=False)
    owner_phone = Column(String(20), nullable=False)
    owner_email = Column(String(100))
    address_text = Column(String(500))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    category = Column(Enum(ShopCategory), default=ShopCategory.B)
    monthly_fee = Column(Float, default=0.0)
    status = Column(Enum(ShopStatus), default=ShopStatus.ACTIVE)
    qr_code_data = Column(String(500))
    ussd_string = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    district = relationship("District", back_populates="shops")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50))
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ============================================================
# الأمان
# ============================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class RBAC:
    ROLES = {
        "governor": ["read:all", "write:all", "delete:all"],
        "district_mayor": ["read:district", "write:district"],
        "collector": ["read:assigned", "write:collection"],
    }
    @staticmethod
    def has_permission(user_role: str, required_permission: str) -> bool:
        return required_permission in RBAC.ROLES.get(user_role, [])

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ============================================================
# نماذج Pydantic
# ============================================================
class UserBase(BaseModel):
    phone: str
    full_name: str
    role: UserRole
    district_id: Optional[int] = None
class UserCreate(UserBase):
    password: str
class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True
class Token(BaseModel):
    access_token: str
    token_type: str
class DistrictBase(BaseModel):
    code: str
    name: str
    mayor_name: Optional[str] = None
    mayor_phone: Optional[str] = None
class DistrictCreate(DistrictBase):
    pass
class DistrictResponse(DistrictBase):
    id: int
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True
class ShopBase(BaseModel):
    commercial_name: str
    activity_type: str
    commercial_register: Optional[str] = None
    owner_name: str
    owner_phone: str
    owner_email: Optional[str] = None
    address_text: Optional[str] = None
    latitude: float
    longitude: float
    category: ShopCategory = ShopCategory.B
    monthly_fee: float
class ShopCreate(ShopBase):
    district_id: int
class ShopResponse(ShopBase):
    id: int
    unique_code: str
    district_id: int
    status: ShopStatus
    qr_code_data: Optional[str] = None
    ussd_string: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True
class AlertRequest(BaseModel):
    level: str
    message: str
    district_id: Optional[int] = None
    shop_id: Optional[int] = None

# ============================================================
# خدمة التنبيهات
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_sovereign_alert(level: str, message: str, district_id: int = None, shop_id: int = None):
    log_message = (
        f"🚨 [SOVEREIGN ALERT] Level: {level} | "
        f"To: {settings.SOVEREIGN_MOBILE} | "
        f"District: {district_id} | Shop: {shop_id} | "
        f"Message: {message}"
    )
    logger.warning(log_message)
    return {"status": "logged", "to": settings.SOVEREIGN_MOBILE}

# ============================================================
# دوال مساعدة
# ============================================================
def generate_unique_code(district_code: str, db: Session) -> str:
    last = db.query(Shop).filter(Shop.unique_code.like(f"{district_code}-%")).order_by(Shop.id.desc()).first()
    if last:
        num = int(last.unique_code.split("-")[-1]) + 1
    else:
        num = 1
    return f"{district_code}-{num:04d}"

# ============================================================
# إنشاء التطبيق
# ============================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="نظام المركز السيادي لإدارة إيرادات محافظة عدن"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# ============================================================
# الواجهة الرئيسية (HTML) - ديوان مضبوط
# ============================================================
@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ديوان محافظة عدن - المركز السيادي</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                background: linear-gradient(135deg, #0a1128 0%, #1c3b4e 100%);
                color: #fff;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                text-align: center;
                max-width: 800px;
                padding: 2rem;
                background: rgba(255,255,255,0.08);
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 25px 50px rgba(0,0,0,0.4);
                border: 1px solid rgba(255,255,255,0.15);
            }
            h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                text-shadow: 0 0 20px #00d4ff;
                color: #e0f2fe;
            }
            .subtitle {
                font-size: 1.2rem;
                margin-bottom: 2rem;
                color: #b0c4de;
                letter-spacing: 1px;
            }
            .card {
                background: rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1rem 0;
                display: inline-block;
                width: 100%;
                max-width: 400px;
                text-align: right;
            }
            .card p { margin: 0.5rem 0; }
            .highlight {
                font-size: 2rem;
                font-weight: bold;
                color: #ffd700;
            }
            .btn {
                display: inline-block;
                margin: 1rem 0.5rem;
                padding: 12px 30px;
                background: #ffd700;
                color: #0a1128;
                border: none;
                border-radius: 30px;
                font-size: 1rem;
                font-weight: bold;
                text-decoration: none;
                transition: all 0.3s;
                cursor: pointer;
            }
            .btn:hover {
                background: #ffea00;
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.3);
            }
            .btn-outline {
                background: transparent;
                border: 2px solid #ffd700;
                color: #ffd700;
            }
            .btn-outline:hover {
                background: rgba(255,215,0,0.2);
            }
            footer {
                margin-top: 2rem;
                font-size: 0.85rem;
                color: #8899aa;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🏛️</div>
            <h1>ديوان محافظة عدن</h1>
            <div class="subtitle">المركز السيادي لإدارة الإيرادات والرقابة الميدانية</div>

            <div class="card">
                <p><strong>رقم القيادة السيادي:</strong> <span class="highlight">967770295876</span></p>
                <p><strong>حالة النظام:</strong> 🟢 نشط</p>
                <p id="date-time">تحميل التاريخ...</p>
                <p><strong>مديريات المرحلة الأولى:</strong> المنصورة | خور مكسر</p>
            </div>

            <div>
                <a href="/docs" class="btn">📋 منصة المطورين (API)</a>
                <a href="/health" class="btn btn-outline">💓 فحص الخادم</a>
            </div>

            <footer>
                &copy; 2026 - ديوان محافظة عدن. جميع الحقوق محفوظة.
            </footer>
        </div>

        <script>
            // عرض التاريخ والوقت الحالي
            function updateDateTime() {
                const now = new Date();
                document.getElementById('date-time').innerHTML = 
                    '<strong>الوقت:</strong> ' + 
                    now.toLocaleDateString('ar-EG', { weekday:'long', year:'numeric', month:'long', day:'numeric' }) + 
                    ' | ' + now.toLocaleTimeString('ar-EG');
            }
            updateDateTime();
            setInterval(updateDateTime, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "sovereign-center"}

# ============================================================
# الـ API (النقاط البرمجية)
# ============================================================
API_V1 = settings.API_V1_STR

@app.post(f"{API_V1}/auth/register", response_model=UserResponse, tags=["Authentication"])
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
    hashed = get_password_hash(user_data.password)
    new_user = User(
        phone=user_data.phone, full_name=user_data.full_name,
        hashed_password=hashed, role=user_data.role,
        district_id=user_data.district_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post(f"{API_V1}/auth/login", response_model=Token, tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="رقم الهاتف أو كلمة المرور غير صحيحة")
    access_token = create_access_token(
        data={"sub": user.phone, "role": user.role.value, "district_id": user.district_id}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post(f"{API_V1}/districts/", response_model=DistrictResponse, tags=["Districts"])
def create_district(district: DistrictCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload or not RBAC.has_permission(payload.get("role"), "write:all"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    db_district = District(**district.dict())
    db.add(db_district)
    db.commit()
    db.refresh(db_district)
    return db_district

@app.get(f"{API_V1}/districts/", response_model=List[DistrictResponse], tags=["Districts"])
def list_districts(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    return db.query(District).all()

@app.post(f"{API_V1}/shops/", response_model=ShopResponse, tags=["Shops"])
def create_shop(shop: ShopCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    role = payload.get("role")
    user_district = payload.get("district_id")
    if not (RBAC.has_permission(role, "write:all") or (RBAC.has_permission(role, "write:district") and user_district == shop.district_id)):
        raise HTTPException(status_code=403, detail="غير مصرح")
    district = db.query(District).filter(District.id == shop.district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="المديرية غير موجودة")
    unique_code = generate_unique_code(district.code, db)
    ussd = f"*159*{unique_code.split('-')[-1]}#"
    qr_data = f"ADEN:SHOP:{unique_code}"
    new_shop = Shop(
        **shop.dict(), unique_code=unique_code,
        qr_code_data=qr_data, ussd_string=ussd
    )
    db.add(new_shop)
    db.commit()
    db.refresh(new_shop)
    return new_shop

@app.get(f"{API_V1}/shops/", response_model=List[ShopResponse], tags=["Shops"])
def list_shops(district_id: int = None, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    query = db.query(Shop)
    if district_id:
        query = query.filter(Shop.district_id == district_id)
    return query.all()

@app.post(f"{API_V1}/alerts/test", tags=["Reports & Alerts"])
def test_alert(alert: AlertRequest, token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    send_sovereign_alert(alert.level, alert.message, alert.district_id, alert.shop_id)
    return {"status": "alert sent", "to": settings.SOVEREIGN_MOBILE}

@app.get(f"{API_V1}/reports/daily-summary", tags=["Reports & Alerts"])
def daily_summary(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    districts = db.query(District).all()
    summary = []
    for d in districts:
        shops_count = db.query(Shop).filter(Shop.district_id == d.id).count()
        summary.append({"district": d.name, "shops": shops_count})
    return {"date": datetime.now().strftime("%Y-%m-%d"), "districts": summary, "sovereign_mobile": settings.SOVEREIGN_MOBILE}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

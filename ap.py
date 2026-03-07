from flask import Flask, request, jsonify
import json
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ==================== إعداد Google Drive ====================
SERVICE_ACCOUNT_FILE = 'supermarket-service-account.json'  # ضع اسم ملف JSON هنا
FOLDER_NAME = 'supermarket-db'  # اسم المجلد الذي شاركته مع Service Account

scope = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=scope
)

client = gspread.authorize(creds)

# فتح الملف أو إنشاؤه
try:
    sheet = client.open(FOLDER_NAME).sheet1
except gspread.SpreadsheetNotFound:
    sheet = client.create(FOLDER_NAME).sheet1
    sheet.append_row(["data"])
    sheet.append_row([json.dumps({"products":[], "customers":[]})])

# ==================== دوال قراءة وكتابة البيانات ====================
def load_data():
    data = sheet.get_all_records()
    if data:
        return json.loads(data[0]["data"])
    return {"products":[], "customers":[]}

def save_data(data):
    sheet.update("A2", [[json.dumps(data)]])

# ==================== صفحات التطبيق ====================
@app.route("/")
def home():
    return "Supermarket System Running 🚀"

# عرض المنتجات
@app.route("/products")
def products():
    data = load_data()
    return jsonify(data["products"])

# إضافة منتج (لوحة المدير)
@app.route("/admin/add", methods=["POST"])
def add_product():
    password = request.form.get("password")
    if password != "12345":
        return "Wrong password"

    name = request.form.get("name")
    price = request.form.get("price")

    data = load_data()
    data["products"].append({
        "name": name,
        "price": price
    })
    save_data(data)
    return "Product Added ✅"

# عرض الزبائن
@app.route("/admin/customers")
def customers():
    data = load_data()
    return jsonify(data["customers"])

# إضافة زبون وجمع نقاط
@app.route("/customer/add", methods=["POST"])
def add_customer():
    phone = request.form.get("phone")
    points = int(request.form.get("points", 0))

    data = load_data()
    found = False
    for c in data["customers"]:
        if c["phone"] == phone:
            c["points"] += points
            found = True
            break
    if not found:
        data["customers"].append({"phone": phone, "points": points})

    save_data(data)
    return "Customer Updated ✅"

# ==================== تشغيل التطبيق ====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

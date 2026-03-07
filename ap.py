from flask import Flask, request, jsonify
import gspread
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'  # هذا ملف OAuth من حسابك
TOKEN_FILE = 'token.json'
FOLDER_NAME = 'supermarket-db'

# ---- إعداد Google Drive API ----
def get_gspread_client():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return gspread.authorize(creds)

client = get_gspread_client()

# فتح أو إنشاء ملف البيانات
try:
    sheet = client.open(FOLDER_NAME).sheet1
except gspread.SpreadsheetNotFound:
    sheet = client.create(FOLDER_NAME).sheet1
    sheet.append_row(["data"])
    sheet.append_row([json.dumps({"products":[], "customers":[]})])

def load_data():
    data = sheet.get_all_records()
    if data:
        return json.loads(data[0]["data"])
    return {"products":[], "customers":[]}

def save_data(data):
    sheet.update("A2", [[json.dumps(data)]])

# ---- Routes ----
@app.route("/")
def home():
    return "Supermarket System Running 🚀"

@app.route("/products")
def products():
    data = load_data()
    return jsonify(data["products"])

@app.route("/admin/add", methods=["POST"])
def add_product():
    password = request.form.get("password")
    if password != "12345":
        return "Wrong password"
    name = request.form.get("name")
    price = request.form.get("price")
    data = load_data()
    data["products"].append({"name": name, "price": price})
    save_data(data)
    return "Product Added ✅"

@app.route("/admin/customers")
def customers():
    data = load_data()
    return jsonify(data["customers"])

@app.route("/customer/add", methods=["POST"])
def add_customer():
    phone = request.form.get("phone")
    points = int(request.form.get("points",0))
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

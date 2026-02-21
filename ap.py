from flask import Flask, render_template_string, request, redirect, session, url_for
import os
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = "verysecretkey123"  # 🔐 لتشفير الجلسة

# -------------------------
# ربط قاعدة بيانات PostgreSQL
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL غير معرف في Environment Variables")

# تحليل الرابط للحصول على معلومات الاتصال
url = urlparse(DATABASE_URL)
DB_CONFIG = {
    "dbname": url.path[1:],
    "user": url.username,
    "password": url.password,
    "host": url.hostname,
    "port": url.port
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

# -------------------------
# تهيئة قاعدة البيانات
# -------------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            price REAL,
            category_id INTEGER REFERENCES categories(id)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# -------------------------
# الصفحة الرئيسية (واجهة الزبون)
# -------------------------
@app.route("/", methods=["GET"])
def home():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()

    products_by_category = {}
    for cat in categories:
        cur.execute("SELECT * FROM products WHERE category_id=%s", (cat[0],))
        products_by_category[cat[0]] = cur.fetchall()

    cur.close()
    conn.close()
    return render_template_string(CUSTOMER_TEMPLATE,
                                  categories=categories,
                                  products_by_category=products_by_category)

# -------------------------
# تسجيل الدخول للمدير
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "123456":
            session["logged_in"] = True
            return redirect("/admin")
        else:
            error = "اسم المستخدم أو كلمة المرور خاطئة"
    return render_template_string(LOGIN_TEMPLATE, error=error)

# -------------------------
# لوحة المدير
# -------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        if "category_name" in request.form:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", (request.form["category_name"],))
        if "product_name" in request.form:
            cur.execute(
                "INSERT INTO products (name, price, category_id) VALUES (%s, %s, %s)",
                (request.form["product_name"], request.form["price"], request.form["category_id"])
            )
        conn.commit()

    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()

    cur.execute("""
        SELECT products.id, products.name, products.price, categories.name
        FROM products
        JOIN categories ON products.category_id = categories.id
    """)
    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template_string(ADMIN_TEMPLATE,
                                  categories=categories,
                                  products=products)

# -------------------------
# حذف فئة / منتج
# -------------------------
@app.route("/delete_category/<int:id>")
def delete_category(id):
    if not session.get("logged_in"):
        return redirect("/login")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")

@app.route("/delete_product/<int:id>")
def delete_product(id):
    if not session.get("logged_in"):
        return redirect("/login")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")

# -------------------------
# تسجيل الخروج
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------------
# قوالب HTML
# -------------------------
CUSTOMER_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>سوبر ماركت أولاد قايد</title>
<style>
body{background:#000;color:#FFD700;font-family:Tahoma;margin:0;padding:0}
header{text-align:center;padding:20px}
h1{margin:0}
.category{margin:15px;padding:10px;border:1px solid #FFD700}
.product{display:flex;justify-content:space-between;margin:5px 0}
button{background:#FFD700;color:black;border:none;padding:5px 10px;cursor:pointer}
input{padding:5px;margin:3px 0;width:95%}
footer{text-align:center;margin-top:30px;padding:20px;border-top:1px solid #FFD700;font-size:12px}
.admin-btn{margin-top:20px;padding:10px 20px;background:#FFD700;color:black;border:none;cursor:pointer}
</style>
<script>
let cart=[];
function addToCart(name,price){
    cart.push({name:name,price:price});
    alert("تمت الإضافة للسلة");
}
function showInvoice(){
    let customer=document.getElementById("customer").value;
    let phone=document.getElementById("phone").value;
    let location=document.getElementById("location").value;
    if(!customer || !phone || !location){
        alert("يرجى إدخال بياناتك كاملة");
        return;
    }
    let text="🛒 سوبر ماركت أولاد قايد محمد\\n";
    text+="الاسم: "+customer+"\\n";
    text+="الرقم: "+phone+"\\n";
    text+="الموقع: "+location+"\\n\\n";
    let total=0;
    cart.forEach(item=>{
        text+=item.name+" - "+item.price+" ريال\\n";
        total+=parseFloat(item.price);
    });
    text+="\\nالإجمالي: "+total+" ريال";
    window.open("https://wa.me/967770295876?text="+encodeURIComponent(text));
}
function openAdmin(){ window.location.href="/login"; }
</script>
</head>
<body>
<header>
<h1>سوبر ماركت أولاد قايد محمد</h1>
<p>أولاد قايد للتجارة العامة</p>
</header>
<div style="padding:15px">
{% for cat in categories %}
<div class="category">
<h3>{{cat[1]}}</h3>
{% for p in products_by_category[cat[0]] %}
<div class="product">
<span>{{p[1]}} - {{p[2]}} ريال</span>
<button onclick="addToCart('{{p[1]}}','{{p[2]}}')">إضافة</button>
</div>
{% endfor %}
</div>
{% endfor %}
<h3>بيانات الزبون</h3>
<input id="customer" placeholder="اسمك"><br>
<input id="phone" placeholder="رقمك"><br>
<input id="location" placeholder="موقعك"><br><br>
<button onclick="showInvoice()">ارسال الى واتساب</button>
<br>
<button class="admin-btn" onclick="openAdmin()">لوحة المدير</button>
</div>
<footer>
📍 الازرق / موعد حماده : حبيل تود<br>
لصاحبها «فايز / وإخوانه»<br>
إعداد وتصميم «م / وسيم العامري»<br>
للتواصل 967770295876
</footer>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>تسجيل دخول المدير</title>
<style>
body{font-family:Tahoma;background:#000;color:#FFD700;text-align:center;padding:50px}
input{padding:5px;margin:5px;width:200px}
button{padding:5px 10px;background:#FFD700;color:black;border:none;cursor:pointer}
.error{color:red;margin:10px}
</style>
</head>
<body>
<h2>تسجيل دخول المدير</h2>
<form method="POST">
<input name="username" placeholder="اسم المستخدم"><br>
<input type="password" name="password" placeholder="كلمة المرور"><br>
<button>دخول</button>
</form>
<div class="error">{{error}}</div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>لوحة المدير</title>
<style>input, select{margin:5px;padding:5px}</style>
</head>
<body>
<h2>إضافة فئة</h2>
<form method="POST">
<input name="category_name" placeholder="اسم الفئة">
<button>إضافة</button>
</form>
<h2>إضافة منتج</h2>
<form method="POST">
<input name="product_name" placeholder="اسم المنتج">
<input name="price" placeholder="السعر">
<select name="category_id">
{% for c in categories %}
<option value="{{c[0]}}">{{c[1]}}</option>
{% endfor %}
</select>
<button>إضافة</button>
</form>
<h2>الفئات</h2>
{% for c in categories %}
{{c[1]}} <a href="/delete_category/{{c[0]}}">حذف</a><br>
{% endfor %}
<h2>المنتجات</h2>
{% for p in products %}
{{p[1]}} - {{p[2]}} ريال ({{p[3]}})
<a href="/delete_product/{{p[0]}}">حذف</a><br>
{% endfor %}
<br><a href="/logout">تسجيل الخروج</a>
</body>
</html>
"""

# -------------------------
# تشغيل التطبيق
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

# app.py
from flask import Flask, render_template_string, request, redirect, session, url_for, flash
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "supermarket_secret_key_2026"

# -------------------------
# الاتصال بقاعدة البيانات PostgreSQL
# -------------------------
DB_URL = os.getenv("DATABASE_URL")  # URL من Environment Variable

def get_connection():
    return psycopg2.connect(DB_URL)

# -------------------------
# تهيئة قاعدة البيانات
# -------------------------
def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category_id INTEGER REFERENCES categories(id)
    )
    """)
    conn.commit()
    c.close()
    conn.close()

init_db()

# -------------------------
# الصفحة الرئيسية للزبائن
# -------------------------
@app.route("/")
def home():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY name")
    categories = c.fetchall()

    products_by_category = {}
    for cat in categories:
        c.execute("SELECT * FROM products WHERE category_id=%s ORDER BY name", (cat[0],))
        products_by_category[cat[0]] = c.fetchall()

    conn.close()

    return render_template_string(HOME_TEMPLATE,
                                  categories=categories,
                                  products_by_category=products_by_category)

# -------------------------
# تسجيل الدخول
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == "admin" and password == "123456":
            session["logged_in"] = True
            flash("تم تسجيل الدخول بنجاح", "success")
            return redirect("/admin")
        else:
            error = "اسم المستخدم أو كلمة المرور غير صحيحة"
    return render_template_string(LOGIN_TEMPLATE, error=error)

# -------------------------
# لوحة الإدارة
# -------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = get_connection()
    c = conn.cursor()

    if request.method == "POST":
        # إضافة فئة جديدة
        if "category_name" in request.form and request.form["category_name"].strip() != "":
            c.execute("INSERT INTO categories (name) VALUES (%s)", (request.form["category_name"],))
            flash("تمت إضافة الفئة بنجاح", "success")
        # إضافة منتج جديد
        if "product_name" in request.form and request.form["product_name"].strip() != "":
            c.execute("INSERT INTO products (name, price, category_id) VALUES (%s,%s,%s)",
                      (request.form["product_name"],
                       float(request.form["price"]),
                       int(request.form["category_id"])))
            flash("تمت إضافة المنتج بنجاح", "success")
        conn.commit()

    # جلب البيانات للعرض
    c.execute("SELECT * FROM categories ORDER BY name")
    categories = c.fetchall()

    c.execute("""
    SELECT products.id, products.name, products.price, categories.name
    FROM products
    JOIN categories ON products.category_id = categories.id
    ORDER BY products.name
    """)
    products = c.fetchall()
    conn.close()

    return render_template_string(ADMIN_TEMPLATE, categories=categories, products=products)

# -------------------------
# حذف
# -------------------------
@app.route("/delete_category/<int:id>")
def delete_category(id):
    if not session.get("logged_in"):
        return redirect("/login")
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("تم حذف الفئة بنجاح", "warning")
    return redirect("/admin")

@app.route("/delete_product/<int:id>")
def delete_product(id):
    if not session.get("logged_in"):
        return redirect("/login")
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("تم حذف المنتج بنجاح", "warning")
    return redirect("/admin")

@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج", "info")
    return redirect("/")

# -------------------------
# قوالب HTML مع Bootstrap
# -------------------------

HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>سوبر ماركت أولاد قايد</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
<style>
body { background-color: #000; color: #FFD700; }
h1, h3 { text-align:center; }
hr { border-color: #FFD700; }
a { color: #FFD700; }
</style>
</head>
<body>
<div class="container mt-4">
<h1>سوبر ماركت أولاد قايد محمد</h1>
{% for cat in categories %}
<div class="card bg-dark text-warning mb-3">
  <div class="card-header">{{cat[1]}}</div>
  <div class="card-body">
    {% for p in products_by_category[cat[0]] %}
    <p>{{p[1]}} - {{p[2]}} ريال</p>
    {% endfor %}
  </div>
</div>
{% endfor %}
<div class="text-center"><a href="/login" class="btn btn-warning text-dark">لوحة المدير</a></div>
</div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تسجيل الدخول</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
<style>body{background-color:#000;color:#FFD700;}</style>
</head>
<body>
<div class="container mt-5">
<h2>تسجيل الدخول</h2>
<form method="POST" class="mb-3">
<div class="mb-3"><input name="username" class="form-control" placeholder="اسم المستخدم"></div>
<div class="mb-3"><input type="password" name="password" class="form-control" placeholder="كلمة المرور"></div>
<button class="btn btn-warning text-dark">دخول</button>
</form>
{% if error %}<div class="alert alert-danger">{{error}}</div>{% endif %}
</div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>لوحة الإدارة</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
<style>body{background-color:#000;color:#FFD700;}</style>
</head>
<body>
<div class="container mt-4">
<h2>لوحة الإدارة</h2>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    {% for category, message in messages %}
      <div class="alert alert-{{ category }}">{{ message }}</div>
    {% endfor %}
  {% endif %}
{% endwith %}

<h3>إضافة فئة جديدة</h3>
<form method="POST" class="mb-4">
<div class="input-group">
<input name="category_name" class="form-control" placeholder="اسم الفئة">
<button class="btn btn-warning text-dark">إضافة</button>
</div>
</form>

<h3>إضافة منتج جديد</h3>
<form method="POST" class="mb-4">
<div class="input-group mb-2">
<input name="product_name" class="form-control" placeholder="اسم المنتج">
<input name="price" class="form-control" placeholder="السعر">
<select name="category_id" class="form-select">
{% for c in categories %}
<option value="{{c[0]}}">{{c[1]}}</option>
{% endfor %}
</select>
<button class="btn btn-warning text-dark">إضافة</button>
</div>
</form>

<h3>المنتجات الحالية</h3>
<table class="table table-dark table-striped">
<thead>
<tr>
<th>الاسم</th><th>السعر</th><th>الفئة</th><th>حذف</th>
</tr>
</thead>
<tbody>
{% for p in products %}
<tr>
<td>{{p[1]}}</td>
<td>{{p[2]}}</td>
<td>{{p[3]}}</td>
<td><a href="/delete_product/{{p[0]}}" class="btn btn-danger btn-sm">حذف</a></td>
</tr>
{% endfor %}
</tbody>
</table>

<div class="mt-3">
<a href="/logout" class="btn btn-secondary">تسجيل الخروج</a>
</div>

</div>
</body>
</html>
"""

# -------------------------
# تشغيل التطبيق
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

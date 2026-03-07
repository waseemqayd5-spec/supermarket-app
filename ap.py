import os
import sqlite3
import psycopg2
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = "qaid_mohammed_final_secure_key"

# --- إعدادات قاعدة البيانات ---
# الرابط يتم جلبه تلقائياً من Render إذا قمت بإنشاء قاعدة بيانات PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    try:
        if DATABASE_URL:
            # PostgreSQL للإنتاج (Render)
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        else:
            # SQLite للتطوير المحلي
            conn = sqlite3.connect('supermarket.db')
            conn.row_factory = sqlite3.Row
            return conn
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute('''CREATE TABLE IF NOT EXISTS categories (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL UNIQUE)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS products (
                            id SERIAL PRIMARY KEY,
                            category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                            name TEXT NOT NULL,
                            price REAL NOT NULL,
                            quantity TEXT)''')
        else:
            cur.execute('''CREATE TABLE IF NOT EXISTS categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS products (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category_id INTEGER,
                            name TEXT NOT NULL,
                            price REAL NOT NULL,
                            quantity TEXT,
                            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE)''')
        conn.commit()
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
    finally:
        cur.close()
        conn.close()

# تهيئة قاعدة البيانات عند بدء التشغيل
init_db()

# --- واجهة الزبون (التصميم الأسود والذهبي) ---
CUSTOMER_UI = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>سوبر ماركت أولاد قايد محمد</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #0b0b0b; color: #d4af37; margin: 0; }
        .gold-border { border-color: #d4af37; }
        .gold-bg { background-color: #d4af37; color: #000; }
        .card { background: #1a1a1a; border: 1px solid #d4af37; border-radius: 15px; }
        .category-tab { cursor: pointer; padding: 12px 25px; border-bottom: 3px solid transparent; white-space: nowrap; color: #aaa; }
        .category-tab.active { border-bottom: 3px solid #d4af37; font-weight: bold; color: #d4af37; background: rgba(212, 175, 55, 0.1); }
        #cart-modal { display: none; background: rgba(0,0,0,0.95); position: fixed; inset: 0; z-index: 100; overflow-y: auto; }
        .logo-circle { width: 100px; height: 100px; border: 2px solid #d4af37; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: white; margin: 0 auto; color: #000; font-weight: bold; text-align: center; font-size: 11px; }
    </style>
</head>
<body class="pb-32">
    <header class="text-center py-8 bg-black border-b-2 gold-border">
        <h1 class="text-2xl font-bold mb-1">سوبر ماركت أولاد قايد محمد</h1>
        <p class="text-sm text-gray-400 mb-4">للتجارة العامة</p>
        <div class="logo-circle">اولاد قايد<br>للتجاره العامه</div>
    </header>

    <nav class="sticky top-0 bg-black z-50 border-b gold-border overflow-x-auto flex" id="category-bar">
        <div class="category-tab active" onclick="filterCategory(0, this)">الكل</div>
        {% for cat in categories %}
        <div class="category-tab" onclick="filterCategory({{cat[0] if DATABASE_URL else cat['id']}}, this)">{{cat[1] if DATABASE_URL else cat['name']}}</div>
        {% endfor %}
    </nav>

    <main class="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
        {% for prod in products %}
        <div class="card p-4 product-item" data-category="{{prod[1] if DATABASE_URL else prod['category_id']}}">
            <h3 class="text-lg font-bold mb-1 text-white">{{prod[2] if DATABASE_URL else prod['name']}}</h3>
            <p class="text-gray-500 text-xs mb-3">{{prod[4] if DATABASE_URL else prod['quantity']}}</p>
            <div class="flex justify-between items-center">
                <span class="text-lg font-bold text-yellow-500">{{prod[3] if DATABASE_URL else prod['price']}} ريال</span>
                <button onclick="addToCart({{prod[0] if DATABASE_URL else prod['id']}}, '{{prod[2] if DATABASE_URL else prod['name']}}', {{prod[3] if DATABASE_URL else prod['price']}})" class="gold-bg px-4 py-1.5 rounded-full font-bold text-sm">إضافة +</button>
            </div>
        </div>
        {% endfor %}
    </main>

    <footer class="mt-12 p-6 border-t gold-border text-center bg-black text-xs">
        <p>الموقع: الأزرق / موعد حمادة : حبيل تود</p>
        <p class="text-gray-500 mt-1">لصاحبها: « فايز / وإخوانه »</p>
        <div class="mt-4 opacity-70">إعداد وتصميم « م / وسيم العامري » | 967770295876</div>
    </footer>

    <div class="fixed bottom-0 w-full bg-black border-t gold-border p-4 flex justify-between items-center z-50">
        <div class="ps-2">
            <span id="cart-total" class="text-lg font-bold text-white">0</span> <small>ريال</small>
        </div>
        <button onclick="toggleCart()" class="gold-bg px-6 py-2 rounded-full font-bold shadow-lg">🛒 السلة (<span id="cart-count">0</span>)</button>
    </div>

    <div id="cart-modal">
        <div class="max-w-md mx-auto bg-black border-2 gold-border rounded-xl m-4 mt-10 p-5">
            <div class="flex justify-between items-center mb-4 border-b gold-border pb-2">
                <h2 class="text-xl font-bold">المشتريات</h2>
                <button onclick="toggleCart()" class="text-red-500 text-2xl">&times;</button>
            </div>
            <div id="cart-items" class="space-y-3 mb-6 max-h-60 overflow-y-auto"></div>
            <div class="space-y-3">
                <input type="text" id="cust-name" placeholder="اسم الزبون" class="w-full p-2 bg-gray-900 rounded border gold-border text-white">
                <input type="tel" id="cust-phone" placeholder="رقم الهاتف" class="w-full p-2 bg-gray-900 rounded border gold-border text-white">
                <button onclick="sendToWhatsApp()" class="w-full bg-green-600 text-white py-3 rounded-lg font-bold">إرسال للواتساب</button>
            </div>
        </div>
    </div>

    <script>
        let cart = [];
        function filterCategory(id, el) {
            document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.product-item').forEach(item => {
                if (id === 0 || item.dataset.category == id) item.style.display = 'block';
                else item.style.display = 'none';
            });
        }
        function addToCart(id, name, price) {
            let item = cart.find(i => i.id === id);
            if (item) item.qty++; else cart.push({id, name, price, qty: 1});
            updateUI();
        }
        function updateUI() {
            document.getElementById('cart-count').innerText = cart.reduce((a, b) => a + b.qty, 0);
            document.getElementById('cart-total').innerText = cart.reduce((a, b) => a + (b.price * b.qty), 0);
            const container = document.getElementById('cart-items');
            container.innerHTML = cart.map((item, idx) => `
                <div class="flex justify-between items-center bg-gray-900 p-2 rounded text-sm">
                    <span>${item.name}</span>
                    <div class="flex items-center gap-2">
                        <button onclick="changeQty(${idx}, -1)" class="w-6 h-6 bg-red-900 rounded">-</button>
                        <span>${item.qty}</span>
                        <button onclick="changeQty(${idx}, 1)" class="w-6 h-6 bg-green-900 rounded">+</button>
                    </div>
                </div>
            `).join('');
        }
        function changeQty(idx, delta) {
            cart[idx].qty += delta; if (cart[idx].qty <= 0) cart.splice(idx, 1);
            updateUI();
        }
        function toggleCart() {
            const m = document.getElementById('cart-modal');
            m.style.display = m.style.display === 'block' ? 'none' : 'block';
        }
        function sendToWhatsApp() {
            const name = document.getElementById('cust-name').value;
            const phone = document.getElementById('cust-phone').value;
            if(!name || !phone) { alert("أدخل الاسم والرقم"); return; }
            let msg = `🛒 *طلب جديد من أولاد قايد محمد*\\nزبون: ${name}\\nجوال: ${phone}\\n------------------\\n`;
            cart.forEach(i => msg += `• ${i.name} (${i.qty}) = ${i.price * i.qty} ريال\\n`);
            msg += `------------------\\n💰 *الإجمالي: ${document.getElementById('cart-total').innerText} ريال*`;
            window.open(`https://wa.me/967770295876?text=${encodeURIComponent(msg)}`, '_blank');
        }
    </script>
</body>
</html>
"""

# واجهة الإدارة
ADMIN_UI = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>لوحة التحكم</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="p-4 bg-gray-100 font-sans">
    <div class="max-w-4xl mx-auto bg-white p-6 rounded shadow-lg">
        <div class="flex justify-between mb-6 border-b pb-4">
            <h1 class="text-xl font-bold">إدارة المتجر</h1>
            <a href="/" class="text-blue-600 font-bold border border-blue-600 px-4 py-1 rounded">عرض الموقع</a>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <section>
                <h2 class="font-bold mb-2">1. إضافة فئة</h2>
                <form action="/admin/add_category" method="POST" class="flex gap-1 mb-4">
                    <input type="text" name="name" placeholder="بهارات، معلبات..." class="border p-2 flex-1 rounded" required>
                    <button class="bg-green-600 text-white px-3 rounded text-sm">إضافة</button>
                </form>
                <div class="bg-gray-50 p-2 rounded max-h-40 overflow-y-auto">
                    {% for cat in categories %}
                    <div class="flex justify-between text-xs mb-1 p-1 border-b">
                        <span>{{cat[1] if DATABASE_URL else cat['name']}}</span>
                        <a href="/admin/del_category/{{cat[0] if DATABASE_URL else cat['id']}}" class="text-red-500">حذف</a>
                    </div>
                    {% endfor %}
                </div>
            </section>
            <section>
                <h2 class="font-bold mb-2">2. إضافة منتج</h2>
                <form action="/admin/add_product" method="POST" class="space-y-2">
                    <select name="category_id" class="w-full border p-2 rounded" required>
                        <option value="">اختر الفئة</option>
                        {% for cat in categories %}<option value="{{cat[0] if DATABASE_URL else cat['id']}}">{{cat[1] if DATABASE_URL else cat['name']}}</option>{% endfor %}
                    </select>
                    <input type="text" name="name" placeholder="اسم المنتج" class="w-full border p-2 rounded" required>
                    <input type="number" name="price" placeholder="السعر" class="w-full border p-2 rounded" required>
                    <input type="text" name="quantity" placeholder="الوصف (كجم/كيس)" class="w-full border p-2 rounded">
                    <button class="w-full bg-blue-600 text-white py-2 rounded font-bold">حفظ المنتج</button>
                </form>
            </section>
        </div>
        <div class="mt-8 border-t pt-4">
            <h2 class="font-bold mb-4">قائمة المنتجات الحالية</h2>
            <table class="w-full text-right text-sm">
                <tr class="bg-gray-200">
                    <th class="p-2">المنتج</th><th class="p-2">السعر</th><th class="p-2">الفئة</th><th class="p-2">حذف</th>
                </tr>
                {% for p in products %}
                <tr class="border-b">
                    <td class="p-2">{{p[2] if DATABASE_URL else p['name']}}</td>
                    <td class="p-2 font-bold">{{p[3] if DATABASE_URL else p['price']}}</td>
                    <td class="p-2 text-gray-500">{{p[5] if DATABASE_URL else p['cat_name']}}</td>
                    <td class="p-2"><a href="/admin/del_product/{{p[0] if DATABASE_URL else p['id']}}" class="text-red-500">حذف</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""

# --- المسارات (Routes) ---

@app.route('/')
def index():
    conn = get_db_connection()
    if not conn: return "خطأ في قاعدة البيانات"
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY name")
    cats = cur.fetchall()
    cur.execute("SELECT p.*, c.name as cat_name FROM products p JOIN categories c ON p.category_id = c.id ORDER BY p.id DESC")
    prods = cur.fetchall()
    cur.close(); conn.close()
    return render_template_string(CUSTOMER_UI, categories=cats, products=prods, DATABASE_URL=DATABASE_URL)

@app.route('/admin')
def admin_panel():
    conn = get_db_connection()
    if not conn: return "خطأ في قاعدة البيانات"
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY name")
    cats = cur.fetchall()
    cur.execute("SELECT p.*, c.name as cat_name FROM products p JOIN categories c ON p.category_id = c.id ORDER BY p.id DESC")
    prods = cur.fetchall()
    cur.close(); conn.close()
    return render_template_string(ADMIN_UI, categories=cats, products=prods, DATABASE_URL=DATABASE_URL)

@app.route('/admin/add_category', methods=['POST'])
def add_cat():
    name = request.form.get('name')
    if name:
        conn = get_db_connection(); cur = conn.cursor()
        try:
            sql = "INSERT INTO categories (name) VALUES (%s)" if DATABASE_URL else "INSERT INTO categories (name) VALUES (?)"
            cur.execute(sql, (name,))
            conn.commit()
        finally: cur.close(); conn.close()
    return redirect('/admin')

@app.route('/admin/del_category/<int:id>')
def del_cat(id):
    conn = get_db_connection(); cur = conn.cursor()
    try:
        sql = "DELETE FROM categories WHERE id = %s" if DATABASE_URL else "DELETE FROM categories WHERE id = ?"
        cur.execute(sql, (id,))
        conn.commit()
    finally: cur.close(); conn.close()
    return redirect('/admin')

@app.route('/admin/add_product', methods=['POST'])
def add_prod():
    cid, name, price, qty = request.form.get('category_id'), request.form.get('name'), request.form.get('price'), request.form.get('quantity')
    if cid and name and price:
        conn = get_db_connection(); cur = conn.cursor()
        try:
            sql = "INSERT INTO products (category_id, name, price, quantity) VALUES (%s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO products (category_id, name, price, quantity) VALUES (?, ?, ?, ?)"
            cur.execute(sql, (cid, name, price, qty))
            conn.commit()
        finally: cur.close(); conn.close()
    return redirect('/admin')

@app.route('/admin/del_product/<int:id>')
def del_prod(id):
    conn = get_db_connection(); cur = conn.cursor()
    try:
        sql = "DELETE FROM products WHERE id = %s" if DATABASE_URL else "DELETE FROM products WHERE id = ?"
        cur.execute(sql, (id,))
        conn.commit()
    finally: cur.close(); conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    # للتشغيل المحلي فقط
    app.run(debug=True, host='0.0.0.0', port=5000)

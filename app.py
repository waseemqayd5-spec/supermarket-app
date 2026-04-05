import os
import re
import json
import time
import math
import socket
import sqlite3
import threading
import statistics
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template_string, request

# =========================================================
# إعدادات عامة
# =========================================================
APP_NAME = "AI Device / Host Monitor"
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "monitor.db")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))
CONNECT_TIMEOUT = float(os.getenv("CONNECT_TIMEOUT", "3"))
READ_TIMEOUT = float(os.getenv("READ_TIMEOUT", "5"))
HISTORY_WINDOW = int(os.getenv("HISTORY_WINDOW", "20"))
ALERT_SCORE_THRESHOLD = float(os.getenv("ALERT_SCORE_THRESHOLD", "1.8"))

# Targets أمثلة:
# TARGETS="https://example.com,8.8.8.8:53,google.com:443,http://httpbin.org/get"
TARGETS = os.getenv("TARGETS", "https://example.com,8.8.8.8:53")

# Telegram اختياري
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# للتشغيل اليدوي لفحص فوري من API
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

app = Flask(__name__)

# =========================================================
# أدوات مساعدة
# =========================================================
def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def is_ip(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return True
    except OSError:
        return False


def resolve_ip(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except Exception:
        return "unknown"


def send_telegram_alert(message: str):
    if not TELEGRAM_ENABLED:
        return False, "Telegram disabled"

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Missing Telegram credentials"

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        return resp.ok, resp.text
    except Exception as e:
        return False, str(e)


def parse_targets(raw: str):
    """
    يدعم:
    - https://example.com
    - http://example.com/path
    - 8.8.8.8:53
    - google.com:443
    - example.com   -> TCP على 80
    """
    items = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        if re.match(r"^https?://", part, re.IGNORECASE):
            u = urlparse(part)
            scheme = u.scheme.lower()
            host = u.hostname
            port = u.port or (443 if scheme == "https" else 80)
            label = part
            items.append({
                "target_key": part,
                "label": label,
                "mode": "http",
                "scheme": scheme,
                "host": host,
                "port": port,
                "url": part
            })
        else:
            # host:port أو host فقط
            if ":" in part:
                host, port = part.rsplit(":", 1)
                try:
                    port = int(port)
                except ValueError:
                    port = 80
            else:
                host = part
                port = 80

            label = f"{host}:{port}"
            items.append({
                "target_key": label,
                "label": label,
                "mode": "tcp",
                "scheme": "tcp",
                "host": host,
                "port": port,
                "url": None
            })

    return items


# =========================================================
# قاعدة البيانات
# =========================================================
class DB:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_key TEXT UNIQUE,
                label TEXT,
                mode TEXT,
                scheme TEXT,
                host TEXT,
                port INTEGER,
                first_seen TEXT,
                last_seen TEXT,
                last_status TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                target_key TEXT,
                label TEXT,
                mode TEXT,
                host TEXT,
                port INTEGER,
                resolved_ip TEXT,
                online INTEGER,
                latency_ms REAL,
                http_status INTEGER,
                failure_streak INTEGER,
                anomaly_score REAL,
                classification TEXT,
                reason TEXT,
                details TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                target_key TEXT,
                label TEXT,
                anomaly_score REAL,
                reason TEXT,
                status TEXT
            )
            """)

            self.conn.commit()

    def upsert_target(self, t, status):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM targets WHERE target_key = ?", (t["target_key"],))
            found = cur.fetchone()
            ts = now_str()

            if found:
                cur.execute("""
                    UPDATE targets
                    SET label=?, mode=?, scheme=?, host=?, port=?, last_seen=?, last_status=?
                    WHERE target_key=?
                """, (
                    t["label"], t["mode"], t["scheme"], t["host"], t["port"], ts, status, t["target_key"]
                ))
                is_new = False
            else:
                cur.execute("""
                    INSERT INTO targets
                    (target_key, label, mode, scheme, host, port, first_seen, last_seen, last_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    t["target_key"], t["label"], t["mode"], t["scheme"], t["host"], t["port"], ts, ts, status
                ))
                is_new = True

            self.conn.commit()
            return is_new

    def log_scan(self, row):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO scan_logs (
                    timestamp, target_key, label, mode, host, port, resolved_ip,
                    online, latency_ms, http_status, failure_streak,
                    anomaly_score, classification, reason, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["timestamp"],
                row["target_key"],
                row["label"],
                row["mode"],
                row["host"],
                row["port"],
                row["resolved_ip"],
                int(row["online"]),
                row["latency_ms"],
                row["http_status"],
                row["failure_streak"],
                row["anomaly_score"],
                row["classification"],
                row["reason"],
                json.dumps(row, ensure_ascii=False)
            ))
            self.conn.commit()

    def log_alert(self, target_key, label, score, reason, status="sent"):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO alerts (timestamp, target_key, label, anomaly_score, reason, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now_str(), target_key, label, score, reason, status))
            self.conn.commit()

    def recent_logs(self, target_key, limit=20):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT * FROM scan_logs
                WHERE target_key = ?
                ORDER BY id DESC
                LIMIT ?
            """, (target_key, limit))
            return cur.fetchall()

    def latest_status(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT s.*
                FROM scan_logs s
                INNER JOIN (
                    SELECT target_key, MAX(id) AS max_id
                    FROM scan_logs
                    GROUP BY target_key
                ) x
                ON s.target_key = x.target_key AND s.id = x.max_id
                ORDER BY s.target_key
            """)
            return cur.fetchall()

    def recent_alerts(self, limit=50):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT * FROM alerts
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return cur.fetchall()

    def recent_activity(self, limit=100):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT * FROM scan_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return cur.fetchall()


db = DB(DB_PATH)

# =========================================================
# محرك التصنيف الذكي
# =========================================================
class SimpleAIClassifier:
    """
    مصنف خفيف:
    - طبيعي
    - مشبوه
    اعتمادًا على:
    - فشل متكرر
    - ارتفاع غير طبيعي في latency
    - HTTP 5xx
    - Target جديد
    """

    def __init__(self, history_window=20, threshold=1.8):
        self.history_window = history_window
        self.threshold = threshold

    def _mean_std(self, values):
        if not values:
            return 0.0, 1.0
        if len(values) == 1:
            return float(values[0]), 1.0
        mean = statistics.mean(values)
        std = statistics.pstdev(values)
        if std < 0.001:
            std = 1.0
        return mean, std

    def score(self, current, history_rows, is_new=False):
        latencies = []
        failures = []
        online_vals = []

        for row in history_rows:
            lat = safe_float(row["latency_ms"], 0.0)
            latencies.append(lat)
            failures.append(int(row["failure_streak"]))
            online_vals.append(int(row["online"]))

        mean_lat, std_lat = self._mean_std(latencies)
        mean_fail, std_fail = self._mean_std(failures)

        score = 0.0
        reasons = []

        # 1) target جديد
        if is_new:
            score += 0.7
            reasons.append("تمت إضافة Target جديد لأول مرة")

        # 2) target offline
        if not current["online"]:
            score += 0.8
            reasons.append("الهدف لا يستجيب")

        # 3) فشل متكرر
        if current["failure_streak"] >= 2:
            score += 0.9
            reasons.append("تكرار الفشل في الفحص")

        # 4) ارتفاع latency بشكل شاذ
        if current["online"] and len(latencies) >= 5 and current["latency_ms"] > 0:
            z = abs((current["latency_ms"] - mean_lat) / std_lat)
            if z >= 2.5:
                score += min(z / 2.0, 1.5)
                reasons.append("ارتفاع غير طبيعي في زمن الاستجابة")

        # 5) HTTP 5xx
        if current["http_status"] is not None and current["http_status"] >= 500:
            score += 1.0
            reasons.append("الخدمة رجعت HTTP 5xx")

        classification = "طبيعي"
        if score >= self.threshold:
            classification = "مشبوه"

        if not reasons:
            reasons.append("لا يوجد سلوك مقلق")

        return round(score, 3), classification, "، ".join(dict.fromkeys(reasons))


classifier = SimpleAIClassifier(HISTORY_WINDOW, ALERT_SCORE_THRESHOLD)

# =========================================================
# الفاحص
# =========================================================
class MonitorService:
    def __init__(self):
        self.stop_event = threading.Event()
        self.failure_streak = {}
        self.scan_lock = threading.Lock()
        self.last_scan_started = None
        self.last_scan_finished = None
        self.last_scan_count = 0

    def probe_tcp(self, host, port):
        started = time.time()
        resolved_ip = resolve_ip(host)
        try:
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
            sock.close()
            latency_ms = (time.time() - started) * 1000.0
            return {
                "online": True,
                "latency_ms": round(latency_ms, 2),
                "resolved_ip": resolved_ip,
                "http_status": None,
                "details": f"TCP connection successful to {host}:{port}"
            }
        except Exception as e:
            latency_ms = (time.time() - started) * 1000.0
            return {
                "online": False,
                "latency_ms": round(latency_ms, 2),
                "resolved_ip": resolved_ip,
                "http_status": None,
                "details": f"TCP connection failed: {str(e)}"
            }

    def probe_http(self, url, host, port):
        started = time.time()
        resolved_ip = resolve_ip(host)
        try:
            resp = requests.get(
                url,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=True,
                headers={"User-Agent": "Render-Monitor/1.0"}
            )
            latency_ms = (time.time() - started) * 1000.0
            online = True  # أي رد HTTP يعتبر الخدمة reachable
            return {
                "online": online,
                "latency_ms": round(latency_ms, 2),
                "resolved_ip": resolved_ip,
                "http_status": resp.status_code,
                "details": f"HTTP GET success: {resp.status_code}"
            }
        except Exception as e:
            latency_ms = (time.time() - started) * 1000.0
            return {
                "online": False,
                "latency_ms": round(latency_ms, 2),
                "resolved_ip": resolved_ip,
                "http_status": None,
                "details": f"HTTP GET failed: {str(e)}"
            }

    def probe_target(self, t):
        if t["mode"] == "http":
            return self.probe_http(t["url"], t["host"], t["port"])
        return self.probe_tcp(t["host"], t["port"])

    def maybe_alert(self, row):
        if row["classification"] != "مشبوه":
            return

        message = (
            "🚨 تنبيه من نظام المراقبة\n"
            f"الوقت: {row['timestamp']}\n"
            f"الهدف: {row['label']}\n"
            f"الحالة: {row['classification']}\n"
            f"Score: {row['anomaly_score']}\n"
            f"السبب: {row['reason']}\n"
            f"Resolved IP: {row['resolved_ip']}\n"
            f"Latency: {row['latency_ms']} ms\n"
            f"HTTP Status: {row['http_status']}"
        )

        print("\n" + "=" * 70)
        print(message)
        print("=" * 70 + "\n")

        ok, resp = send_telegram_alert(message)
        db.log_alert(
            row["target_key"],
            row["label"],
            row["anomaly_score"],
            row["reason"],
            status="sent" if ok else f"failed: {resp}"
        )

    def scan_once(self):
        with self.scan_lock:
            self.last_scan_started = now_str()

            targets = parse_targets(TARGETS)
            count = 0

            for t in targets:
                result = self.probe_target(t)
                count += 1

                key = t["target_key"]

                if result["online"]:
                    self.failure_streak[key] = 0
                    status = "online"
                else:
                    self.failure_streak[key] = self.failure_streak.get(key, 0) + 1
                    status = "offline"

                is_new = db.upsert_target(t, status=status)
                history = db.recent_logs(key, limit=HISTORY_WINDOW)

                row = {
                    "timestamp": now_str(),
                    "target_key": key,
                    "label": t["label"],
                    "mode": t["mode"],
                    "host": t["host"],
                    "port": t["port"],
                    "resolved_ip": result["resolved_ip"],
                    "online": result["online"],
                    "latency_ms": result["latency_ms"],
                    "http_status": result["http_status"],
                    "failure_streak": self.failure_streak.get(key, 0),
                }

                score, classification, reason = classifier.score(row, history, is_new=is_new)
                row["anomaly_score"] = score
                row["classification"] = classification
                row["reason"] = reason
                row["details"] = result["details"]

                db.log_scan(row)
                self.maybe_alert(row)

            self.last_scan_count = count
            self.last_scan_finished = now_str()

    def run_forever(self):
        while not self.stop_event.is_set():
            try:
                self.scan_once()
            except Exception as e:
                print(f"[ERROR] scan failed: {e}")
            self.stop_event.wait(SCAN_INTERVAL)


monitor = MonitorService()
_background_started = False
_background_lock = threading.Lock()


def start_background_monitor():
    global _background_started
    with _background_lock:
        if _background_started:
            return
        thread = threading.Thread(target=monitor.run_forever, daemon=True)
        thread.start()
        _background_started = True


start_background_monitor()

# =========================================================
# واجهة الويب
# =========================================================
DASHBOARD_HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="utf-8">
    <title>{{ app_name }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body{
            font-family: Arial, sans-serif;
            background:#0f172a;
            color:#e5e7eb;
            margin:0;
            padding:20px;
        }
        .wrap{max-width:1200px;margin:auto;}
        .title{
            display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;
            margin-bottom:20px;
        }
        .box{
            background:#111827;border:1px solid #1f2937;border-radius:16px;padding:16px;margin-bottom:16px;
            box-shadow:0 8px 20px rgba(0,0,0,.25);
        }
        .grid{
            display:grid;
            grid-template-columns:repeat(auto-fit, minmax(250px, 1fr));
            gap:16px;
        }
        .card{
            background:#111827;border:1px solid #1f2937;border-radius:16px;padding:16px;
        }
        .ok{color:#22c55e;font-weight:bold;}
        .bad{color:#ef4444;font-weight:bold;}
        .warn{color:#f59e0b;font-weight:bold;}
        table{
            width:100%;
            border-collapse:collapse;
            overflow:hidden;
        }
        th,td{
            border-bottom:1px solid #1f2937;
            padding:10px;
            text-align:right;
            font-size:14px;
        }
        th{color:#93c5fd;background:#0b1220;}
        code{
            background:#0b1220;padding:2px 6px;border-radius:6px;
        }
        .muted{color:#9ca3af;}
        .btn{
            display:inline-block;padding:10px 14px;background:#2563eb;color:#fff;text-decoration:none;border-radius:10px;
        }
        .small{font-size:13px;}
    </style>
</head>
<body>
<div class="wrap">
    <div class="title">
        <div>
            <h1>{{ app_name }}</h1>
            <div class="muted">لوحة مراقبة وتشخيص ذكي - Render Ready</div>
        </div>
        <div class="small">
            <div>آخر فحص بدأ: <code>{{ meta.last_scan_started or '—' }}</code></div>
            <div>آخر فحص انتهى: <code>{{ meta.last_scan_finished or '—' }}</code></div>
            <div>عدد الأهداف: <code>{{ meta.last_scan_count }}</code></div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>إجمالي الأهداف</h3>
            <div style="font-size:30px">{{ stats.total }}</div>
        </div>
        <div class="card">
            <h3>طبيعي</h3>
            <div class="ok" style="font-size:30px">{{ stats.normal }}</div>
        </div>
        <div class="card">
            <h3>مشبوه</h3>
            <div class="bad" style="font-size:30px">{{ stats.suspicious }}</div>
        </div>
        <div class="card">
            <h3>Offline</h3>
            <div class="warn" style="font-size:30px">{{ stats.offline }}</div>
        </div>
    </div>

    <div class="box">
        <h2>الحالة الحالية</h2>
        <table>
            <thead>
                <tr>
                    <th>الهدف</th>
                    <th>Mode</th>
                    <th>IP</th>
                    <th>Online</th>
                    <th>Latency</th>
                    <th>HTTP</th>
                    <th>Failure Streak</th>
                    <th>Score</th>
                    <th>Classification</th>
                    <th>Reason</th>
                    <th>الوقت</th>
                </tr>
            </thead>
            <tbody>
            {% for row in latest %}
                <tr>
                    <td>{{ row["label"] }}</td>
                    <td>{{ row["mode"] }}</td>
                    <td>{{ row["resolved_ip"] }}</td>
                    <td>{% if row["online"] %}<span class="ok">Yes</span>{% else %}<span class="bad">No</span>{% endif %}</td>
                    <td>{{ row["latency_ms"] }} ms</td>
                    <td>{{ row["http_status"] if row["http_status"] is not none else "-" }}</td>
                    <td>{{ row["failure_streak"] }}</td>
                    <td>{{ row["anomaly_score"] }}</td>
                    <td>
                        {% if row["classification"] == "مشبوه" %}
                            <span class="bad">{{ row["classification"] }}</span>
                        {% else %}
                            <span class="ok">{{ row["classification"] }}</span>
                        {% endif %}
                    </td>
                    <td>{{ row["reason"] }}</td>
                    <td>{{ row["timestamp"] }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="box">
        <h2>آخر التنبيهات</h2>
        <table>
            <thead>
                <tr>
                    <th>الوقت</th>
                    <th>الهدف</th>
                    <th>Score</th>
                    <th>السبب</th>
                    <th>الحالة</th>
                </tr>
            </thead>
            <tbody>
            {% for a in alerts %}
                <tr>
                    <td>{{ a["timestamp"] }}</td>
                    <td>{{ a["label"] }}</td>
                    <td>{{ a["anomaly_score"] }}</td>
                    <td>{{ a["reason"] }}</td>
                    <td>{{ a["status"] }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="box">
        <h2>إعدادات التشغيل</h2>
        <p><b>TARGETS</b>: <code>{{ targets }}</code></p>
        <p><b>SCAN_INTERVAL</b>: <code>{{ scan_interval }}</code> ثانية</p>
        <p><b>DB_PATH</b>: <code>{{ db_path }}</code></p>
        <p><b>Telegram</b>: <code>{{ telegram_enabled }}</code></p>
        <p><a class="btn" href="/api/status">API Status</a></p>
    </div>
</div>
</body>
</html>
"""


@app.route("/")
def index():
    latest = db.latest_status()
    alerts = db.recent_alerts(20)

    total = len(latest)
    normal = sum(1 for x in latest if x["classification"] == "طبيعي")
    suspicious = sum(1 for x in latest if x["classification"] == "مشبوه")
    offline = sum(1 for x in latest if not x["online"])

    return render_template_string(
        DASHBOARD_HTML,
        app_name=APP_NAME,
        latest=latest,
        alerts=alerts,
        stats={
            "total": total,
            "normal": normal,
            "suspicious": suspicious,
            "offline": offline,
        },
        meta={
            "last_scan_started": monitor.last_scan_started,
            "last_scan_finished": monitor.last_scan_finished,
            "last_scan_count": monitor.last_scan_count,
        },
        targets=TARGETS,
        scan_interval=SCAN_INTERVAL,
        db_path=DB_PATH,
        telegram_enabled=TELEGRAM_ENABLED,
    )


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": APP_NAME,
        "time": now_str(),
        "last_scan_started": monitor.last_scan_started,
        "last_scan_finished": monitor.last_scan_finished,
        "last_scan_count": monitor.last_scan_count,
    })


@app.route("/api/status")
def api_status():
    latest = db.latest_status()
    return jsonify({
        "service": APP_NAME,
        "time": now_str(),
        "targets": parse_targets(TARGETS),
        "last_scan_started": monitor.last_scan_started,
        "last_scan_finished": monitor.last_scan_finished,
        "last_scan_count": monitor.last_scan_count,
        "latest": [dict(x) for x in latest],
    })


@app.route("/api/logs")
def api_logs():
    limit = int(request.args.get("limit", "100"))
    rows = db.recent_activity(limit=limit)
    return jsonify({
        "count": len(rows),
        "items": [dict(x) for x in rows]
    })


@app.route("/api/alerts")
def api_alerts():
    limit = int(request.args.get("limit", "50"))
    rows = db.recent_alerts(limit=limit)
    return jsonify({
        "count": len(rows),
        "items": [dict(x) for x in rows]
    })


@app.route("/api/scan-now", methods=["POST"])
def api_scan_now():
    if ADMIN_TOKEN:
        header_token = request.headers.get("X-Admin-Token", "")
        if header_token != ADMIN_TOKEN:
            return jsonify({"ok": False, "error": "unauthorized"}), 401

    try:
        monitor.scan_once()
        return jsonify({
            "ok": True,
            "message": "scan completed",
            "time": now_str()
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

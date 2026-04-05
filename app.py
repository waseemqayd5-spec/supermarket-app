import os
import re
import sys
import json
import time
import math
import queue
import sqlite3
import socket
import platform
import ipaddress
import subprocess
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# ===============================
# إعدادات المشروع
# ===============================
CONFIG = {
    "network_cidr": "192.168.1.0/24",   # غيّره حسب شبكتك
    "scan_interval_seconds": 60,
    "sqlite_db": "device_monitor.db",
    "history_window": 20,
    "new_device_is_suspicious": True,
    "failed_ping_threshold": 3,
    "burst_device_threshold": 25,
    "enable_console_alert": True,

    # Telegram اختياري
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": ""
    },

    # Email اختياري
    "email": {
        "enabled": False,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_email": "",
        "to_email": ""
    }
}

# ===============================
# أدوات عامة
# ===============================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def hostname_from_ip(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "unknown"


def ping_ip(ip, timeout=1000):
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout), ip]
    else:
        # لينكس / ماك
        seconds = str(max(1, int(timeout / 1000)))
        cmd = ["ping", "-c", "1", "-W", seconds, ip]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        success = result.returncode == 0
        latency_ms = extract_latency_ms(output)
        ttl = extract_ttl(output)
        return success, latency_ms, ttl, output
    except Exception as e:
        return False, 0.0, -1, str(e)


def extract_latency_ms(text):
    patterns = [
        r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
        r"tempo[=<]\s*(\d+(?:\.\d+)?)\s*ms",
        r"Average\s*=\s*(\d+)ms"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return safe_float(m.group(1), 0.0)
    return 0.0


def extract_ttl(text):
    m = re.search(r"ttl[=:\s](\d+)", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return -1


def guess_os_from_ttl(ttl):
    if ttl < 0:
        return "unknown"
    if ttl <= 64:
        return "Linux/Unix/Android"
    if ttl <= 128:
        return "Windows"
    return "Network Device / Other"


def get_mac_from_arp(ip):
    system = platform.system().lower()
    try:
        if system == "windows":
            result = subprocess.run(["arp", "-a", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            result = subprocess.run(["arp", "-n", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        mac = extract_mac(output)
        return mac if mac else "unknown"
    except Exception:
        return "unknown"


def extract_mac(text):
    mac_patterns = [
        r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})",
        r"([0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}"
    ]
    for p in mac_patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None


def send_telegram_alert(message):
    cfg = CONFIG["telegram"]
    if not cfg.get("enabled"):
        return False, "Telegram disabled"
    token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()
    if not token or not chat_id:
        return False, "Missing Telegram settings"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = f"chat_id={chat_id}&text={message}"
    try:
        import urllib.request
        req = urllib.request.Request(url, data=data.encode("utf-8"), method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, str(e)


def send_email_alert(subject, message):
    cfg = CONFIG["email"]
    if not cfg.get("enabled"):
        return False, "Email disabled"

    required = ["smtp_server", "smtp_port", "username", "password", "from_email", "to_email"]
    if any(not str(cfg.get(k, "")).strip() for k in required):
        return False, "Missing email settings"

    try:
        msg = MIMEMultipart()
        msg["From"] = cfg["from_email"]
        msg["To"] = cfg["to_email"]
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain", "utf-8"))

        server = smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"]))
        server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["from_email"], cfg["to_email"], msg.as_string())
        server.quit()
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


def alert_suspicious(device, reason, anomaly_score):
    message = (
        "🚨 تنبيه: تم اكتشاف جهاز مشبوه\n"
        f"الوقت: {now_str()}\n"
        f"IP: {device.get('ip')}\n"
        f"MAC: {device.get('mac')}\n"
        f"Hostname: {device.get('hostname')}\n"
        f"OS Guess: {device.get('os_guess')}\n"
        f"Latency: {device.get('latency_ms')} ms\n"
        f"Score: {anomaly_score:.3f}\n"
        f"السبب: {reason}"
    )
    if CONFIG.get("enable_console_alert", True):
        print("\n" + "=" * 70)
        print(message)
        print("=" * 70 + "\n")

    send_telegram_alert(message)
    send_email_alert("[ALERT] Suspicious Device Activity", message)


# ===============================
# قاعدة البيانات
# ===============================
class DB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT UNIQUE,
                    mac TEXT,
                    hostname TEXT,
                    os_guess TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    total_seen_count INTEGER DEFAULT 0,
                    total_failed_pings INTEGER DEFAULT 0,
                    last_status TEXT DEFAULT 'unknown'
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ip TEXT,
                    mac TEXT,
                    hostname TEXT,
                    os_guess TEXT,
                    online INTEGER,
                    latency_ms REAL,
                    ttl INTEGER,
                    failed_ping_streak INTEGER,
                    device_count_in_scan INTEGER,
                    anomaly_score REAL,
                    classification TEXT,
                    reason TEXT,
                    raw_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ip TEXT,
                    mac TEXT,
                    hostname TEXT,
                    anomaly_score REAL,
                    reason TEXT,
                    status TEXT
                )
                """
            )
            self.conn.commit()

    def upsert_device(self, ip, mac, hostname, os_guess, status, failed_increment=0):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM devices WHERE ip = ?", (ip,))
            row = cur.fetchone()
            ts = now_str()
            if row:
                cur.execute(
                    """
                    UPDATE devices
                    SET mac = ?, hostname = ?, os_guess = ?, last_seen = ?,
                        total_seen_count = total_seen_count + 1,
                        total_failed_pings = total_failed_pings + ?,
                        last_status = ?
                    WHERE ip = ?
                    """,
                    (mac, hostname, os_guess, ts, failed_increment, status, ip)
                )
                is_new = False
            else:
                cur.execute(
                    """
                    INSERT INTO devices (ip, mac, hostname, os_guess, first_seen, last_seen, total_seen_count, total_failed_pings, last_status)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (ip, mac, hostname, os_guess, ts, ts, failed_increment, status)
                )
                is_new = True
            self.conn.commit()
            return is_new

    def log_activity(self, payload):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO activity_logs (
                    timestamp, ip, mac, hostname, os_guess, online, latency_ms, ttl,
                    failed_ping_streak, device_count_in_scan, anomaly_score,
                    classification, reason, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["timestamp"], payload["ip"], payload["mac"], payload["hostname"],
                    payload["os_guess"], int(payload["online"]), payload["latency_ms"], payload["ttl"],
                    payload["failed_ping_streak"], payload["device_count_in_scan"], payload["anomaly_score"],
                    payload["classification"], payload["reason"], json.dumps(payload, ensure_ascii=False)
                )
            )
            self.conn.commit()

    def log_alert(self, ip, mac, hostname, anomaly_score, reason):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO alerts (timestamp, ip, mac, hostname, anomaly_score, reason, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now_str(), ip, mac, hostname, anomaly_score, reason, "sent")
            )
            self.conn.commit()

    def recent_logs_for_device(self, ip, limit=20):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT * FROM activity_logs
                WHERE ip = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (ip, limit)
            )
            return cur.fetchall()

    def all_devices(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM devices ORDER BY ip")
            return cur.fetchall()


# ===============================
# نموذج AI خفيف داخل نفس الملف
# الفكرة: baseline + anomaly score
# ===============================
class SimpleAnomalyModel:
    def __init__(self, history_window=20):
        self.history_window = history_window

    def _mean_std(self, values):
        if not values:
            return 0.0, 1.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / max(1, len(values))
        std = math.sqrt(var) if var > 1e-9 else 1.0
        return mean, std

    def score(self, current, history_rows, is_new_device=False, burst=False):
        latencies = []
        faileds = []
        online_vals = []

        for row in history_rows:
            latencies.append(safe_float(row["latency_ms"], 0.0))
            faileds.append(int(row["failed_ping_streak"]))
            online_vals.append(int(row["online"]))

        mean_lat, std_lat = self._mean_std(latencies)
        mean_fail, std_fail = self._mean_std(faileds)

        z_latency = abs((current["latency_ms"] - mean_lat) / std_lat) if history_rows else 0.0
        z_failed = abs((current["failed_ping_streak"] - mean_fail) / std_fail) if history_rows else 0.0

        score = 0.0
        reasons = []

        # وزن latency
        if current["latency_ms"] > 0:
            score += min(z_latency / 3.0, 1.5)
            if z_latency >= 3:
                reasons.append("ارتفاع غير طبيعي في زمن الاستجابة")

        # وزن فشل الـ ping
        score += min(z_failed / 2.0, 1.5)
        if current["failed_ping_streak"] >= CONFIG["failed_ping_threshold"]:
            score += 1.2
            reasons.append("تكرار فشل ping بشكل مريب")

        # جهاز جديد
        if is_new_device and CONFIG.get("new_device_is_suspicious", True):
            score += 1.0
            reasons.append("جهاز جديد ظهر في الشبكة")

        # انفجار عدد الأجهزة
        if burst:
            score += 1.0
            reasons.append("زيادة مفاجئة في عدد الأجهزة بالشبكة")

        # MAC غير معروف
        if current["mac"] == "unknown":
            score += 0.4
            reasons.append("تعذر تحديد عنوان MAC")

        # Hostname غير معروف
        if current["hostname"] == "unknown":
            score += 0.2

        # جهاز غير متصل لكن عنده سجل تقلبات كثيرة
        if not current["online"] and current["failed_ping_streak"] >= 2:
            score += 0.6
            reasons.append("الجهاز أصبح غير متاح مع تكرار فشل الاتصال")

        classification = "طبيعي"
        if score >= 1.8:
            classification = "مشبوه"

        reason_text = "، ".join(dict.fromkeys(reasons)) if reasons else "لا يوجد سلوك مقلق"
        return score, classification, reason_text


# ===============================
# الماسح الرئيسي
# ===============================
class DeviceMonitor:
    def __init__(self, config):
        self.config = config
        self.db = DB(config["sqlite_db"])
        self.model = SimpleAnomalyModel(config.get("history_window", 20))
        self.failed_ping_streak = {}

    def scan_network(self):
        net = ipaddress.ip_network(self.config["network_cidr"], strict=False)
        results = []
        lock = threading.Lock()
        q = queue.Queue()

        for ip in net.hosts():
            q.put(str(ip))

        def worker():
            while True:
                try:
                    ip = q.get_nowait()
                except Exception:
                    break
                success, latency_ms, ttl, raw_output = ping_ip(ip)
                if success:
                    host = hostname_from_ip(ip)
                    mac = get_mac_from_arp(ip)
                    os_guess = guess_os_from_ttl(ttl)
                    item = {
                        "ip": ip,
                        "mac": mac,
                        "hostname": host,
                        "os_guess": os_guess,
                        "online": True,
                        "latency_ms": latency_ms,
                        "ttl": ttl,
                        "raw_output": raw_output
                    }
                    with lock:
                        results.append(item)
                q.task_done()

        threads = []
        thread_count = 50
        for _ in range(thread_count):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        q.join()
        return results

    def process_scan(self, scan_results):
        current_online_ips = {d["ip"] for d in scan_results}
        device_count = len(scan_results)
        burst = device_count >= self.config.get("burst_device_threshold", 25)

        # 1) الأجهزة المتصلة الآن
        for device in scan_results:
            ip = device["ip"]
            self.failed_ping_streak[ip] = 0

            is_new = self.db.upsert_device(
                ip=ip,
                mac=device["mac"],
                hostname=device["hostname"],
                os_guess=device["os_guess"],
                status="online",
                failed_increment=0
            )

            history = self.db.recent_logs_for_device(ip, limit=self.config.get("history_window", 20))
            current_payload = {
                "timestamp": now_str(),
                "ip": ip,
                "mac": device["mac"],
                "hostname": device["hostname"],
                "os_guess": device["os_guess"],
                "online": True,
                "latency_ms": device["latency_ms"],
                "ttl": device["ttl"],
                "failed_ping_streak": self.failed_ping_streak.get(ip, 0),
                "device_count_in_scan": device_count
            }
            score, classification, reason = self.model.score(current_payload, history, is_new_device=is_new, burst=burst)
            current_payload["anomaly_score"] = score
            current_payload["classification"] = classification
            current_payload["reason"] = reason

            self.db.log_activity(current_payload)

            if classification == "مشبوه":
                self.db.log_alert(ip, device["mac"], device["hostname"], score, reason)
                alert_suspicious(device, reason, score)

        # 2) الأجهزة المعروفة لكن غير موجودة الآن
        known_devices = self.db.all_devices()
        for row in known_devices:
            ip = row["ip"]
            if ip in current_online_ips:
                continue

            self.failed_ping_streak[ip] = self.failed_ping_streak.get(ip, 0) + 1
            self.db.upsert_device(
                ip=ip,
                mac=row["mac"],
                hostname=row["hostname"],
                os_guess=row["os_guess"],
                status="offline",
                failed_increment=1
            )

            history = self.db.recent_logs_for_device(ip, limit=self.config.get("history_window", 20))
            current_payload = {
                "timestamp": now_str(),
                "ip": ip,
                "mac": row["mac"],
                "hostname": row["hostname"],
                "os_guess": row["os_guess"],
                "online": False,
                "latency_ms": 0.0,
                "ttl": -1,
                "failed_ping_streak": self.failed_ping_streak[ip],
                "device_count_in_scan": device_count
            }
            score, classification, reason = self.model.score(current_payload, history, is_new_device=False, burst=False)
            current_payload["anomaly_score"] = score
            current_payload["classification"] = classification
            current_payload["reason"] = reason

            self.db.log_activity(current_payload)

            if classification == "مشبوه":
                self.db.log_alert(ip, row["mac"], row["hostname"], score, reason)
                alert_suspicious(dict(row), reason, score)

    def print_summary(self):
        devices = self.db.all_devices()
        print("\n" + "-" * 80)
        print(f"ملخص الأجهزة - {now_str()}")
        print("-" * 80)
        if not devices:
            print("لا توجد أجهزة مسجلة حتى الآن.")
            return
        for d in devices:
            print(
                f"IP={d['ip']:<15} | MAC={str(d['mac'])[:17]:<17} | Host={str(d['hostname'])[:20]:<20} | "
                f"OS={str(d['os_guess'])[:20]:<20} | Status={d['last_status']:<7} | "
                f"Seen={d['total_seen_count']:<4} | Failed={d['total_failed_pings']:<4}"
            )
        print("-" * 80 + "\n")

    def run(self):
        print("بدء تشغيل نظام مراقبة الأجهزة الذكي...")
        print(f"الشبكة المستهدفة: {self.config['network_cidr']}")
        print(f"الفاصل الزمني بين كل فحص: {self.config['scan_interval_seconds']} ثانية")
        print(f"قاعدة البيانات: {self.config['sqlite_db']}")
        print("اضغط Ctrl + C للإيقاف.\n")

        while True:
            try:
                start = time.time()
                scan_results = self.scan_network()
                self.process_scan(scan_results)
                self.print_summary()
                elapsed = time.time() - start
                sleep_time = max(1, self.config["scan_interval_seconds"] - int(elapsed))
                print(f"تم اكتشاف {len(scan_results)} جهاز/أجهزة متصلة. الفحص التالي بعد {sleep_time} ثانية.\n")
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                print("\nتم إيقاف النظام بواسطة المستخدم.")
                break
            except Exception as e:
                print(f"خطأ أثناء التشغيل: {e}")
                time.sleep(5)


if __name__ == "__main__":
    # تقدر تغيّر الشبكة من سطر الأوامر
    # مثال: python device_monitor_ai.py 192.168.0.0/24
    if len(sys.argv) > 1:
        CONFIG["network_cidr"] = sys.argv[1]

    monitor = DeviceMonitor(CONFIG)
    monitor.run()

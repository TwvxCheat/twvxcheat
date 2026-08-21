from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import os
import random
import string
import pymysql
import ssl
import traceback
import datetime
from urllib.parse import urlparse, unquote

app = Flask(__name__)

# ================= SECRET & CONFIG =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey_twvx_2026")

ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

LOADER_VERSION = "1.0.0"

# ================= MODELS =================
class KeyModel:
    def __init__(self, id, key_code, key_type='basic', status='active', used_by='-', created_at='', duration_days=30, activated_at=None, expires_at=None, hwid=None, max_devices=1):
        self.id = id
        self.key_code = key_code
        self.key = key_code
        self.key_type = key_type or 'basic'
        self.status = status or 'active'
        self.used_by = used_by or '-'
        self.created_at = created_at
        self.duration_days = duration_days or 30
        self.activated_at = activated_at
        self.expires_at = expires_at
        self.hwid = hwid or ''
        self.max_devices = max_devices or 1
        
        # حساب عدد الأجهزة المسجلة حالياً
        hwid_list = [h.strip() for h in self.hwid.split(',') if h.strip()]
        self.hwid_count = len(hwid_list)

    def __getitem__(self, item):
        if isinstance(item, int):
            arr = [self.id, self.key_code, self.key_type, self.status, self.used_by, self.created_at, self.duration_days, self.activated_at, self.expires_at, self.hwid, self.max_devices]
            return arr[item] if item < len(arr) else ""
        return getattr(self, str(item), "")

class AdminModel:
    def __init__(self, id, username, password, created_at=''):
        self.id = id
        self.username = username
        self.password = password
        self.created_at = created_at

# ================= DB CONNECTION =================
def connect_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None, "لم يتم ضبط متغير DATABASE_URL"
    
    try:
        url = urlparse(db_url)
        db_name = url.path.lstrip('/').split('?')[0]
        password = unquote(url.password) if url.password else ""
        username = unquote(url.username) if url.username else ""

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        conn = pymysql.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=username,
            password=password,
            database=db_name,
            autocommit=True,
            ssl=ctx,
            connect_timeout=10
        )
        return conn, None
    except Exception as e:
        return None, str(e)

# ================= INIT DB =================
def init_db():
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `keys` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `key_code` VARCHAR(255) UNIQUE NOT NULL,
                        `status` VARCHAR(50) DEFAULT 'active',
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                columns_to_add = [
                    ('key_type', "VARCHAR(50) DEFAULT 'basic'"),
                    ('used_by', "VARCHAR(255) DEFAULT '-'"),
                    ('duration_days', "INT DEFAULT 30"),
                    ('activated_at', "DATETIME DEFAULT NULL"),
                    ('expires_at', "DATETIME DEFAULT NULL"),
                    ('hwid', "TEXT DEFAULT NULL"),
                    ('max_devices', "INT DEFAULT 1")
                ]
                for col_name, col_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE `keys` ADD COLUMN `{col_name}` {col_type};")
                    except Exception:
                        pass

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `admins` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `username` VARCHAR(100) UNIQUE NOT NULL,
                        `password` VARCHAR(255) NOT NULL,
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.close()
        except Exception as e:
            print("Init DB Error:", e)

init_db()

def check_admin():
    return session.get("logged_in")

# ================= ROUTES =================

@app.route("/")
def index():
    if check_admin():
        return redirect("/dashboard")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            session["admin_user"] = username
            flash("تم تسجيل الدخول بنجاح 👋", "success")
            return redirect("/dashboard")

        conn, err = connect_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM `admins` WHERE username = %s AND password = %s", (username, password))
                    res = cur.fetchone()
                    if res:
                        session["logged_in"] = True
                        session["admin_user"] = username
                        conn.close()
                        flash("تم تسجيل الدخول بنجاح 👋", "success")
                        return redirect("/dashboard")
                conn.close()
            except Exception:
                pass

        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout", endpoint="logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح 👋", "info")
    return redirect("/login")

@app.route("/dashboard", methods=["GET", "POST"], endpoint="dashboard")
@app.route("/keys", methods=["GET", "POST"], endpoint="keys")
def dashboard():
    if not check_admin():
        return redirect("/login")
    
    if request.method == "POST":
        key_type = request.form.get("key_type", "basic")
        try:
            duration_days = int(request.form.get("duration_days", 30))
            max_devices = int(request.form.get("max_devices", 1))
            count = int(request.form.get("count", 1))
        except ValueError:
            duration_days, max_devices, count = 30, 1, 1

        conn, err = connect_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    for _ in range(count):
                        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                        cur.execute(
                            "INSERT INTO `keys` (`key_code`, `key_type`, `duration_days`, `max_devices`, `status`) VALUES (%s, %s, %s, %s, %s)",
                            (new_key, key_type, duration_days, max_devices, 'active')
                        )
                conn.close()
                flash(f"تم إنشاء {count} مفتاح بحماية ({max_devices} أجهزة لكل مفتاح) بنجاح! 🔑", "success")
            except Exception as e:
                flash(f"خطأ إنشاء المفاتيح: {e}", "danger")
        return redirect("/dashboard")

    keys_list = []
    admins_list = []
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, key_code, key_type, status, used_by, created_at, duration_days, activated_at, expires_at, hwid, max_devices FROM `keys` ORDER BY id DESC")
                rows = cur.fetchall()
                for r in rows:
                    keys_list.append(KeyModel(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]))
                
                cur.execute("SELECT id, username, password, created_at FROM `admins` ORDER BY id DESC")
                adm_rows = cur.fetchall()
                for a in adm_rows:
                    admins_list.append(AdminModel(a[0], a[1], a[2], a[3]))
            conn.close()
        except Exception as e:
            flash(f"خطأ جلب البيانات: {e}", "danger")

    total_keys = len(keys_list)
    used_keys = sum(1 for k in keys_list if k.activated_at is not None)
    available_keys = total_keys - used_keys

    return render_template(
        "dashboard.html",
        keys=keys_list,
        recent_keys=keys_list,
        admins=admins_list,
        total_keys=total_keys,
        used_keys=used_keys,
        available_keys=available_keys,
        current_admin=session.get("admin_user", "Admin")
    )

# ================= ACTIONS =================
@app.route("/reset_hwid/<int:key_id>")
def reset_hwid(key_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE `keys` SET hwid = NULL WHERE id = %s", (key_id,))
            conn.close()
            flash("تم مسح جميع الأجهزة المربوطة بالمفتاح بنجاح 🔄", "success")
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return redirect("/dashboard")

@app.route("/ban/<int:key_id>")
def ban_key(key_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE `keys` SET status = 'banned' WHERE id = %s", (key_id,))
            conn.close()
            flash("تم حظر المفتاح 🚫", "warning")
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return redirect("/dashboard")

@app.route("/pause/<int:key_id>")
def pause_key(key_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE `keys` SET status = 'paused' WHERE id = %s", (key_id,))
            conn.close()
            flash("تم تجميد المفتاح ⏸️", "warning")
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return redirect("/dashboard")

@app.route("/unpause/<int:key_id>")
def unpause_key(key_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE `keys` SET status = 'active' WHERE id = %s", (key_id,))
            conn.close()
            flash("تم تنشيط المفتاح ▶️", "success")
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return redirect("/dashboard")

@app.route("/delete/<int:key_id>")
def delete_key(key_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `keys` WHERE id = %s", (key_id,))
            conn.close()
            flash("تم حذف المفتاح 🗑️", "info")
        except Exception as e:
            flash(f"خطأ الحذف: {e}", "danger")
    return redirect("/dashboard")

@app.route("/add_admin", methods=["POST"])
def add_admin():
    if not check_admin():
        return redirect("/login")
    new_user = request.form.get("new_username", "").strip()
    new_pass = request.form.get("new_password", "").strip()
    if new_user and new_pass:
        conn, err = connect_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO `admins` (`username`, `password`) VALUES (%s, %s)", (new_user, new_pass))
                conn.close()
                flash(f"تمت إضافة الأدمن ({new_user}) 👤", "success")
            except Exception:
                flash("اسم المستخدم موجود سابقاً", "danger")
    return redirect("/dashboard")

@app.route("/delete_admin/<int:admin_id>")
def delete_admin(admin_id):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `admins` WHERE id = %s", (admin_id,))
            conn.close()
            flash("تم حذف الأدمن 🗑️", "warning")
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return redirect("/dashboard")

# ================= API VERIFY (MULTI-DEVICE HWID CHECK) =================
@app.route("/verify", methods=["GET", "POST"])
def verify():
    key = request.args.get("key") or request.form.get("key", "")
    hwid = request.args.get("hwid") or request.form.get("hwid", "")
    user_agent = request.headers.get('User-Agent', '')

    if not key:
        if any(browser in user_agent for browser in ["Mozilla", "Chrome", "Safari", "Edge", "Mobile"]):
            return redirect("/login")
        return "INVALID", 200, {'Content-Type': 'text/plain'}

    conn, err = connect_db()
    if err or not conn:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, duration_days, activated_at, expires_at, hwid, max_devices FROM `keys` WHERE `key_code` = %s", (key,))
            row = cur.fetchone()

            if not row:
                conn.close()
                return "INVALID", 200, {'Content-Type': 'text/plain'}

            key_id, status, duration_days, activated_at, expires_at, db_hwid, max_devices = row
            max_devices = max_devices if max_devices else 1

            if status == 'banned':
                conn.close()
                return "BANNED", 200, {'Content-Type': 'text/plain'}

            if status == 'paused':
                conn.close()
                return "PAUSED", 200, {'Content-Type': 'text/plain'}

            now = datetime.datetime.now()

            # تحويل الأجهزة المسجلة لقائمة
            hwid_list = [h.strip() for h in db_hwid.split(',') if h.strip()] if db_hwid else []

            # تاريخ التفعيل الأول
            if activated_at is None:
                duration = duration_days if duration_days else 30
                exp_date = now + datetime.timedelta(days=duration)
                
                if hwid:
                    hwid_list.append(hwid)
                new_hwid_str = ",".join(hwid_list) if hwid_list else None

                cur.execute(
                    "UPDATE `keys` SET `activated_at` = %s, `expires_at` = %s, `status` = 'active', `hwid` = %s WHERE id = %s",
                    (now, exp_date, new_hwid_str, key_id)
                )
                conn.close()
                return "VALID", 200, {'Content-Type': 'text/plain'}

            # فحص الانتهاء
            if expires_at and now > expires_at:
                cur.execute("UPDATE `keys` SET `status` = 'expired' WHERE id = %s", (key_id,))
                conn.close()
                return "EXPIRED", 200, {'Content-Type': 'text/plain'}

            # فحص وتقييد عدد الأجهزة
            if hwid:
                if hwid in hwid_list:
                    # الجهاز مسجل سابقاً ومسموح له
                    conn.close()
                    return "VALID", 200, {'Content-Type': 'text/plain'}
                else:
                    # جهاز جديد يطلب الدخول
                    if len(hwid_list) < max_devices:
                        hwid_list.append(hwid)
                        new_hwid_str = ",".join(hwid_list)
                        cur.execute("UPDATE `keys` SET `hwid` = %s WHERE id = %s", (new_hwid_str, key_id))
                        conn.close()
                        return "VALID", 200, {'Content-Type': 'text/plain'}
                    else:
                        # تم الوصول للحد الأقصى للأجهزة
                        conn.close()
                        return "MAX_DEVICES_REACHED", 200, {'Content-Type': 'text/plain'}

            conn.close()
            return "VALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

@app.route("/version")
def version():
    return jsonify({"version": LOADER_VERSION, "status": "ONLINE"})

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
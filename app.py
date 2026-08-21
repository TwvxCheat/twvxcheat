from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import random
import string
import pymysql
import ssl
import traceback
import datetime
from urllib.parse import urlparse, unquote

app = Flask(__name__)

# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey_twvx_2026")

# ================= MAIN ADMIN =================
ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

# ================= KEY & ADMIN MODELS =================
class KeyModel:
    def __init__(self, id, key_code, key_type='basic', status='active', used_by='-', created_at='', duration_days=30, activated_at=None, expires_at=None):
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

    def __getitem__(self, item):
        if isinstance(item, int):
            arr = [self.id, self.key_code, self.key_type, self.status, self.used_by, self.created_at, self.duration_days, self.activated_at, self.expires_at]
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
                # جدول المفاتيح
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
                    ('expires_at', "DATETIME DEFAULT NULL")
                ]
                for col_name, col_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE `keys` ADD COLUMN `{col_name}` {col_type};")
                    except Exception:
                        pass

                # جدول الأدمنية الإضافيين
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

# ================= ERROR HANDLER =================
@app.errorhandler(500)
def handle_500_error(e):
    error_details = traceback.format_exc()
    return f"""
    <div style="font-family: monospace; padding: 20px; background: #1e1e1e; color: #ff5555; dir: ltr;">
        <h2>⚠️ App Error (500) Details:</h2>
        <pre>{error_details}</pre>
    </div>
    """, 500

# ================= ROUTES =================

@app.route("/")
def index():
    if check_admin():
        return redirect("/dashboard")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # 1. التحقق من الأدمن الرئيسي
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            session["admin_user"] = username
            return redirect("/dashboard")

        # 2. التحقق من قائمة الأدمنية في قاعدة البيانات
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
                        return redirect("/dashboard")
                conn.close()
            except Exception:
                pass

        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout", endpoint="logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard", methods=["GET", "POST"], endpoint="dashboard")
@app.route("/keys", methods=["GET", "POST"], endpoint="keys")
@app.route("/keys_page", methods=["GET", "POST"], endpoint="keys_page")
def dashboard():
    if not check_admin():
        return redirect("/login")
    
    # إنشاء مفتاح جديد
    if request.method == "POST":
        key_type = request.form.get("key_type", "basic")
        try:
            duration_days = int(request.form.get("duration_days", 30))
        except ValueError:
            duration_days = 30

        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        conn, err = connect_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO `keys` (`key_code`, `key_type`, `duration_days`, `status`) VALUES (%s, %s, %s, %s)",
                        (new_key, key_type, duration_days, 'active')
                    )
                conn.close()
                flash(f"تم إنشاء مفتاح لمدة ({duration_days} يوم) بنجاح: {new_key}", "success")
            except Exception as e:
                flash(f"خطأ أثناء إنشاء المفتاح: {e}", "danger")
        return redirect("/dashboard")

    # جلب المفاتيح والأدمنية
    keys_list = []
    admins_list = []
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # جلب المفاتيح
                cur.execute("SELECT id, key_code, key_type, status, used_by, created_at, duration_days, activated_at, expires_at FROM `keys` ORDER BY id DESC")
                rows = cur.fetchall()
                for r in rows:
                    keys_list.append(KeyModel(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
                
                # جلب الأدمنية
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

# إضافة أدمن جديد
@app.route("/add_admin", methods=["POST"], endpoint="add_admin")
def add_admin():
    if not check_admin():
        return redirect("/login")
    
    new_user = request.form.get("new_username", "").strip()
    new_pass = request.form.get("new_password", "").strip()

    if not new_user or not new_pass:
        flash("يرجى ملء جميع الحقول", "warning")
        return redirect("/dashboard")

    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO `admins` (`username`, `password`) VALUES (%s, %s)", (new_user, new_pass))
            conn.close()
            flash(f"تمت إضافة الأدمن ({new_user}) بنجاح! 👤", "success")
        except Exception as e:
            flash("اسم المستخدم موجود بالفعل أو حدث خطأ", "danger")
    return redirect("/dashboard")

# حذف أدمن
@app.route("/delete_admin/<int:admin_id>", endpoint="delete_admin")
def delete_admin(admin_id=None):
    if not check_admin():
        return redirect("/login")
    
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `admins` WHERE id = %s", (admin_id,))
            conn.close()
            flash("تم حذف الأدمن بنجاح 🗑️", "warning")
        except Exception as e:
            flash(f"خطأ الحذف: {e}", "danger")
    return redirect("/dashboard")

@app.route("/generate", methods=["GET", "POST"], endpoint="generate")
@app.route("/generate_key", methods=["GET", "POST"], endpoint="generate_key")
@app.route("/generate_page", methods=["GET", "POST"], endpoint="generate_page")
def generate_page():
    return redirect("/dashboard")

@app.route("/delete/<int:key_id>", endpoint="delete_key")
@app.route("/delete_key/<int:key_id>", endpoint="delete")
def delete_key(key_id=None):
    if not check_admin():
        return redirect("/login")
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `keys` WHERE id = %s", (key_id,))
            conn.close()
            flash("تم حذف المفتاح 🗑️", "warning")
        except Exception as e:
            flash(f"خطأ الحذف: {e}", "danger")
    return redirect("/dashboard")

# ================= API VERIFY =================
@app.route("/verify", methods=["GET", "POST"], endpoint="verify")
def verify():
    key = request.args.get("key") or request.form.get("key", "")
    if not key:
        return "INVALID", 200, {'Content-Type': 'text/plain'}

    conn, err = connect_db()
    if err or not conn:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, duration_days, activated_at, expires_at FROM `keys` WHERE `key_code` = %s", (key,))
            row = cur.fetchone()

            if not row:
                conn.close()
                return "INVALID", 200, {'Content-Type': 'text/plain'}

            key_id, status, duration_days, activated_at, expires_at = row

            if status == 'expired':
                conn.close()
                return "EXPIRED", 200, {'Content-Type': 'text/plain'}

            now = datetime.datetime.now()

            if activated_at is None:
                duration = duration_days if duration_days else 30
                exp_date = now + datetime.timedelta(days=duration)
                cur.execute(
                    "UPDATE `keys` SET `activated_at` = %s, `expires_at` = %s, `status` = 'active' WHERE id = %s",
                    (now, exp_date, key_id)
                )
                conn.close()
                return "VALID", 200, {'Content-Type': 'text/plain'}

            if expires_at and now > expires_at:
                cur.execute("UPDATE `keys` SET `status` = 'expired' WHERE id = %s", (key_id,))
                conn.close()
                return "EXPIRED", 200, {'Content-Type': 'text/plain'}

            conn.close()
            return "VALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
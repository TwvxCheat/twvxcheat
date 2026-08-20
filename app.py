from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import random
import string
import pymysql
import ssl
import traceback
from urllib.parse import urlparse, unquote

app = Flask(__name__)

# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey_twvx_2026")

# ================= ADMIN =================
ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

# ================= KEY CLASS =================
class KeyModel:
    def __init__(self, id, key_code, key_type='basic', status='active', used_by='-', created_at=''):
        self.id = id
        self.key_code = key_code
        self.key = key_code
        self.key_type = key_type or 'basic'
        self.status = status or 'active'
        self.used_by = used_by or '-'
        self.created_at = created_at

    def __getitem__(self, item):
        if isinstance(item, int):
            arr = [self.id, self.key_code, self.key_type, self.status, self.used_by, self.created_at]
            return arr[item] if item < len(arr) else ""
        return getattr(self, str(item), "")

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

# ================= INIT & MIGRATE DB =================
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
                    ('used_by', "VARCHAR(255) DEFAULT '-'")
                ]
                for col_name, col_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE `keys` ADD COLUMN `{col_name}` {col_type};")
                    except Exception:
                        pass
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
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            return redirect("/dashboard")
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout", endpoint="logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard", methods=["GET", "POST"], endpoint="dashboard")
@app.route("/keys", methods=["GET", "POST"], endpoint="keys")
def dashboard():
    if not check_admin():
        return redirect("/login")
    
    # معالجة توليد مفتاح جديد عند ضغط الزر
    if request.method == "POST":
        key_type = request.form.get("key_type", "basic")
        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        conn, err = connect_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    try:
                        cur.execute("INSERT INTO `keys` (`key_code`, `key_type`, `status`) VALUES (%s, %s, %s)", (new_key, key_type, 'active'))
                    except Exception:
                        cur.execute("INSERT INTO `keys` (`key_code`, `status`) VALUES (%s, %s)", (new_key, 'active'))
                conn.close()
                flash(f"تم إنشاء المفتاح بنجاح: {new_key}", "success")
            except Exception as e:
                flash(f"خطأ أثناء إنشاء المفتاح: {e}", "danger")
        return redirect("/dashboard")

    keys_list = []
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT id, key_code, key_type, status, used_by, created_at FROM `keys` ORDER BY id DESC")
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], r[2], r[3], r[4], r[5]))
                except Exception:
                    cur.execute("SELECT id, key_code, status, created_at FROM `keys` ORDER BY id DESC")
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], 'basic', r[2], '-', r[3]))
            conn.close()
        except Exception as e:
            flash(f"خطأ جلب البيانات: {e}", "danger")

    total_keys = len(keys_list)
    used_keys = sum(1 for k in keys_list if str(k.status).lower() not in ['active', 'valid'])
    available_keys = total_keys - used_keys

    return render_template(
        "dashboard.html",
        keys=keys_list,
        recent_keys=keys_list[:10],
        total_keys=total_keys,
        used_keys=used_keys,
        available_keys=available_keys
    )

@app.route("/delete/<int:key_id>", endpoint="delete_key")
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
            cur.execute("SELECT `status` FROM `keys` WHERE `key_code` = %s AND `status` = 'active'", (key,))
            result = cur.fetchone()
        conn.close()
        return "VALID" if result else "INVALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
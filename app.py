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
        self.key = key_code         # لدعم {{ key.key }}
        self.key_type = key_type or 'basic' # لدعم key.key_type
        self.status = status or 'active'    # active / used
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
                # 1. إنشاء الجدول إذا لم يكن موجوداً
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `keys` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `key_code` VARCHAR(255) UNIQUE NOT NULL,
                        `status` VARCHAR(50) DEFAULT 'active',
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # 2. إضافة الأعمدة الناقصة تلقائياً إلى الجدول الحالي
                columns_to_add = [
                    ('key_type', "VARCHAR(50) DEFAULT 'basic'"),
                    ('used_by', "VARCHAR(255) DEFAULT '-'")
                ]
                for col_name, col_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE `keys` ADD COLUMN `{col_name}` {col_type};")
                    except Exception:
                        pass  # العمود موجود بالفعل
            conn.close()
        except Exception as e:
            print("Init DB Error:", e)

# تشغيل تحديث الجدول عند إقلاع التطبيق
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

@app.route("/dashboard", endpoint="dashboard")
@app.route("/keys", endpoint="keys")
@app.route("/keys_page", endpoint="keys_page")
def dashboard():
    if not check_admin():
        return redirect("/login")
    
    keys_list = []
    conn, err = connect_db()
    
    if err:
        flash(f"تنبيه الاتصال: {err}", "danger")
    elif conn:
        try:
            with conn.cursor() as cur:
                # محاولة جلب البيانات مع الحقول الناقصة
                try:
                    cur.execute("SELECT id, key_code, key_type, status, used_by, created_at FROM `keys` ORDER BY id DESC")
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], r[2], r[3], r[4], r[5]))
                except Exception:
                    # في حال لم تتحدث القاعدة بعد، استعلام احتياطي متوافق
                    cur.execute("SELECT id, key_code, status, created_at FROM `keys` ORDER BY id DESC")
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], 'basic', r[2], '-', r[3]))
            conn.close()
        except Exception as e:
            flash(f"خطأ أثناء جلب البيانات: {e}", "danger")

    total_keys = len(keys_list)
    used_keys = sum(1 for k in keys_list if str(k.status).lower() not in ['active', 'valid'])
    available_keys = total_keys - used_keys
    recent_keys = keys_list[:10]

    return render_template(
        "dashboard.html",
        keys=keys_list,
        recent_keys=recent_keys,
        total_keys=total_keys,
        used_keys=used_keys,
        available_keys=available_keys
    )

@app.route("/generate", methods=["GET", "POST"], endpoint="generate")
@app.route("/generate_key", methods=["GET", "POST"], endpoint="generate_key")
@app.route("/generate_page", methods=["GET", "POST"], endpoint="generate_page")
def generate():
    if not check_admin():
        return redirect("/login")
        
    if request.method == "POST":
        key_type = request.form.get("key_type", "basic")
        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        conn, err = connect_db()
        
        if err:
            flash(f"تعذر إنشاء المفتاح: {err}", "danger")
        elif conn:
            try:
                with conn.cursor() as cur:
                    try:
                        cur.execute("INSERT INTO `keys` (`key_code`, `key_type`, `status`) VALUES (%s, %s, %s)", (new_key, key_type, 'active'))
                    except Exception:
                        cur.execute("INSERT INTO `keys` (`key_code`, `status`) VALUES (%s, %s)", (new_key, 'active'))
                conn.close()
                flash(f"تم إنشاء المفتاح بنجاح: {new_key}", "success")
            except Exception as e:
                flash(f"خطأ الحفظ: {e}", "danger")
        return redirect("/dashboard")
        
    return render_template("generate.html")

@app.route("/delete/<int:key_id>", endpoint="delete_key")
@app.route("/delete/<int:key_id>", endpoint="delete")
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
            flash(f"خطأ أثناء الحذف: {e}", "danger")
            
    return redirect("/dashboard")

@app.route("/search", endpoint="search")
def search():
    if not check_admin():
        return redirect("/login")
        
    q = request.args.get("q", "").strip()
    keys_list = []
    conn, err = connect_db()
    
    if conn:
        try:
            with conn.cursor() as cur:
                try:
                    if q == "":
                        cur.execute("SELECT id, key_code, key_type, status, used_by, created_at FROM `keys` ORDER BY id DESC")
                    else:
                        cur.execute("SELECT id, key_code, key_type, status, used_by, created_at FROM `keys` WHERE `key_code` LIKE %s", ('%' + q + '%',))
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], r[2], r[3], r[4], r[5]))
                except Exception:
                    cur.execute("SELECT id, key_code, status, created_at FROM `keys` WHERE `key_code` LIKE %s", ('%' + q + '%',))
                    rows = cur.fetchall()
                    for r in rows:
                        keys_list.append(KeyModel(r[0], r[1], 'basic', r[2], '-', r[3]))
            conn.close()
        except Exception as e:
            flash(f"خطأ أثناء البحث: {e}", "danger")

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

# ================= VERIFY API (C++) =================
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
        
        if result:
            return "VALID", 200, {'Content-Type': 'text/plain'}
        else:
            return "INVALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 200, {'Content-Type': 'text/plain'}

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
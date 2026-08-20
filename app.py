from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import random
import string
import pymysql
import ssl
from urllib.parse import urlparse, unquote

app = Flask(__name__)

# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= ADMIN =================
ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

# ================= KEY CLASS FOR TEMPLATE COMPATIBILITY =================
class KeyItem:
    """كائن مرن يتوافق مع أي طريقة كتابة داخل dashboard.html"""
    def __init__(self, id, key_code, status='active', created_at=''):
        self.id = id
        self.key_code = key_code
        self.key = key_code
        self.status = status
        self.created_at = created_at

    def __getitem__(self, idx):
        items = [self.id, self.key_code, self.status, self.created_at]
        if isinstance(idx, int):
            return items[idx] if idx < len(items) else ""
        return getattr(self, str(idx), "")

# ================= DB CONNECTION =================
def connect_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    
    try:
        url = urlparse(db_url)
        db_name = url.path.lstrip('/').split('?')[0]
        password = unquote(url.password) if url.password else ""
        username = unquote(url.username) if url.username else ""

        # إعداد SSL آمن لـ Aiven MySQL
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        return pymysql.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=username,
            password=password,
            database=db_name,
            autocommit=True,
            ssl=ctx,
            connect_timeout=10
        )
    except Exception as e:
        print("DB Connection Error:", e)
        return None

# ================= INIT DB =================
def init_db():
    try:
        conn = connect_db()
        if not conn:
            return False
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `keys` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `key_code` VARCHAR(255) UNIQUE NOT NULL,
                    `status` VARCHAR(50) DEFAULT 'active',
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.close()
        return True
    except Exception as e:
        print("DB Init Error:", e)
        return False

init_db()

def check_admin():
    return session.get("logged_in")

# ================= ROUTES =================

@app.route("/")
def index():
    if check_admin():
        return redirect("/dashboard")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# المسار الرئيسي للوحة التحكم
@app.route("/dashboard", endpoint="dashboard")
def dashboard():
    if not check_admin():
        return redirect("/login")
    
    keys_list = []
    try:
        conn = connect_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, key_code, status, created_at FROM `keys` ORDER BY id DESC")
                rows = cur.fetchall()
                for r in rows:
                    keys_list.append(KeyItem(r[0], r[1], r[2], r[3]))
            conn.close()
        else:
            flash("لم يتم الاتصال بقاعدة البيانات. تحقق من رابط DATABASE_URL", "warning")
    except Exception as e:
        flash(f"خطأ في الاستعلام: {e}", "danger")
        
    return render_template("dashboard.html", keys=keys_list)

# توجيه الأسماء المستعارة لوحة التحكم لتجنب BuildError
@app.route("/keys", endpoint="keys")
@app.route("/keys_page", endpoint="keys_page")
def dashboard_aliases():
    return dashboard()

@app.route("/generate", methods=["GET", "POST"], endpoint="generate")
def generate():
    if not check_admin():
        return redirect("/login")
    if request.method == "POST":
        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        try:
            conn = connect_db()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO `keys` (`key_code`, `status`) VALUES (%s, %s)", (new_key, 'active'))
                conn.close()
                flash(f"تم إنشاء المفتاح: {new_key}", "success")
            else:
                flash("خطأ: تعذر الاتصال بقاعدة البيانات", "danger")
        except Exception as e:
            flash(f"خطأ عند إنشاء المفتاح: {e}", "danger")
        return redirect("/dashboard")
    return render_template("generate.html")

@app.route("/generate_key", endpoint="generate_key")
@app.route("/generate_page", endpoint="generate_page")
def generate_aliases():
    return generate()

@app.route("/delete/<int:key_id>", endpoint="delete_key")
@app.route("/delete/<int:key_id>", endpoint="delete")
def delete_key(key_id=None):
    if not check_admin():
        return redirect("/login")
    try:
        conn = connect_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `keys` WHERE id = %s", (key_id,))
            conn.close()
            flash("تم حذف المفتاح 🗑️", "warning")
    except Exception as e:
        flash(f"خطأ أثناء الحذف: {e}", "danger")
    return redirect("/dashboard")

@app.route("/search")
def search():
    if not check_admin():
        return redirect("/login")
    q = request.args.get("q", "").strip()
    keys_list = []
    try:
        conn = connect_db()
        if conn:
            with conn.cursor() as cur:
                if q == "":
                    cur.execute("SELECT id, key_code, status, created_at FROM `keys` ORDER BY id DESC")
                else:
                    cur.execute("SELECT id, key_code, status, created_at FROM `keys` WHERE `key_code` LIKE %s", ('%' + q + '%',))
                rows = cur.fetchall()
                for r in rows:
                    keys_list.append(KeyItem(r[0], r[1], r[2], r[3]))
            conn.close()
    except Exception as e:
        flash(f"خطأ أثناء البحث: {e}", "danger")
    return render_template("dashboard.html", keys=keys_list)

# ================= VERIFY API (C++) =================
@app.route("/verify", methods=["GET", "POST"])
def verify():
    key = request.args.get("key") or request.form.get("key", "")
    if not key:
        return "INVALID", 200, {'Content-Type': 'text/plain'}
    
    try:
        conn = connect_db()
        if not conn:
            return "ERROR", 500, {'Content-Type': 'text/plain'}
            
        with conn.cursor() as cur:
            cur.execute("SELECT `status` FROM `keys` WHERE `key_code` = %s", (key,))
            result = cur.fetchone()
        conn.close()
        
        if result and (result[0] == 'active' or result[0] == 'valid'):
            return "VALID", 200, {'Content-Type': 'text/plain'}
        else:
            return "INVALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 500, {'Content-Type': 'text/plain'}

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

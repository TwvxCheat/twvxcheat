import os
import secrets
import sqlite3
import pymysql
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "twvx_cheat_secret_key_12345")
DB_FILE = "twvx_db.db"

# --- الاتصال بقاعدة البيانات (دعم MySQL و SQLite تلقائياً) ---
def get_db():
    if os.environ.get("DB_HOST"):
        try:
            conn = pymysql.connect(
                host=os.environ.get("DB_HOST"),
                user=os.environ.get("DB_USER", "root"),
                password=os.environ.get("DB_PASSWORD", ""),
                database=os.environ.get("DB_NAME", "twvx_db"),
                port=int(os.environ.get("DB_PORT", 3306)),
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor
            )
            return conn, "mysql"
        except Exception:
            pass

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def query_db(query, args=(), fetchone=False, commit=False):
    conn, db_type = get_db()
    cursor = conn.cursor()
    
    if db_type == "sqlite":
        query = query.replace("%s", "?")
        
    cursor.execute(query, args)
    
    if commit:
        if db_type == "sqlite":
            conn.commit()
        conn.close()
        return None
        
    if fetchone:
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    else:
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

# --- دالة تسجيل التحركات (Logs) ---
def log_action(action, details):
    try:
        query_db("INSERT INTO logs (action, details) VALUES (%s, %s)", (action, details), commit=True)
    except Exception as e:
        print(f"Log Error: {e}")

# --- تهيئة الجداول وترقيتها ---
def init_db():
    conn, db_type = get_db()
    cursor = conn.cursor()
    
    if db_type == "sqlite":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_code TEXT UNIQUE NOT NULL,
                key_type TEXT DEFAULT 'basic',
                created_by TEXT DEFAULT 'Admin',
                status TEXT DEFAULT 'active',
                used_by TEXT DEFAULT '-',
                duration_days INTEGER DEFAULT 30,
                max_devices INTEGER DEFAULT 1,
                hwid TEXT DEFAULT NULL,
                is_frozen INTEGER DEFAULT 0,
                frozen_at DATETIME DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activated_at DATETIME DEFAULT NULL,
                expires_at DATETIME DEFAULT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `keys` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `key_code` VARCHAR(255) UNIQUE NOT NULL,
                `key_type` VARCHAR(50) DEFAULT 'basic',
                `created_by` VARCHAR(100) DEFAULT 'Admin',
                `status` VARCHAR(50) DEFAULT 'active',
                `used_by` VARCHAR(255) DEFAULT '-',
                `duration_days` INT DEFAULT 30,
                `max_devices` INT DEFAULT 1,
                `hwid` TEXT DEFAULT NULL,
                `is_frozen` INT DEFAULT 0,
                `frozen_at` DATETIME DEFAULT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `activated_at` DATETIME DEFAULT NULL,
                `expires_at` DATETIME DEFAULT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `admins` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `username` VARCHAR(100) UNIQUE NOT NULL,
                `password` VARCHAR(255) NOT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `logs` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `action` VARCHAR(100) NOT NULL,
                `details` TEXT NOT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    try:
        cursor.execute("ALTER TABLE keys ADD COLUMN is_frozen INT DEFAULT 0;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE keys ADD COLUMN frozen_at DATETIME DEFAULT NULL;")
    except Exception:
        pass

    existing_admin = query_db("SELECT * FROM admins WHERE username=%s", ("TwvxCheat",), fetchone=True)
    if not existing_admin:
        query_db("INSERT INTO admins (username, password) VALUES (%s, %s)", ("TwvxCheat", "Twvx1"), commit=True)
        
    conn.close()

init_db()

def check_admin():
    return session.get("logged_in") is True

# --- المسارات والصفحات ---

@app.route("/")
def index():
    if check_admin():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        admin = query_db("SELECT * FROM admins WHERE username=%s AND password=%s", (username, password), fetchone=True)
        if admin:
            session["logged_in"] = True
            session["username"] = admin["username"]
            log_action("تسجيل دخول", f"سجل المشرف {username} دخوله إلى اللوحة")
            return redirect(url_for("dashboard"))
            
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    username = session.get("username", "Unregistered")
    log_action("تسجيل خروج", f"قام المشرف {username} بتسجيل الخروج")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard", methods=["GET", "POST"])
@app.route("/keys", methods=["GET", "POST"])
@app.route("/keys_page", methods=["GET", "POST"], endpoint="keys_page")
def dashboard():
    if not check_admin():
        return redirect(url_for("login"))
    
    keys_list = query_db("SELECT * FROM keys ORDER BY id DESC") or []
    admins_list = query_db("SELECT id, username, created_at FROM admins ORDER BY id DESC") or []
    logs_list = query_db("SELECT * FROM logs ORDER BY id DESC LIMIT 50") or []
    
    total_keys = len(keys_list)
    active_keys = sum(1 for k in keys_list if k.get("status") == "active")
    expired_keys = sum(1 for k in keys_list if k.get("status") == "expired")
    banned_keys = sum(1 for k in keys_list if k.get("status") == "banned")
    frozen_keys = sum(1 for k in keys_list if k.get("status") == "frozen" or k.get("is_frozen") == 1)
    used_keys = sum(1 for k in keys_list if k.get("hwid"))

    return render_template(
        "dashboard.html", 
        keys=keys_list,
        admins=admins_list,
        logs=logs_list,
        current_user=session.get("username"),
        total_keys=total_keys,
        active_keys=active_keys,
        expired_keys=expired_keys,
        banned_keys=banned_keys,
        frozen_keys=frozen_keys,
        used_keys=used_keys
    )

@app.route("/add_admin", methods=["POST"])
def add_admin():
    if not check_admin():
        return redirect(url_for("login"))
        
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    admin_user = session.get("username", "Admin")
    
    if username and password:
        try:
            query_db("INSERT INTO admins (username, password) VALUES (%s, %s)", (username, password), commit=True)
            log_action("إضافة أدمن", f"قام المشرف {admin_user} بإضافة الأدمن الجديد ({username})")
            flash(f"تم إنشاء حساب الأدمن '{username}' بنجاح!", "success")
        except Exception:
            flash("اسم المستخدم هذا موجود بالفعل!", "danger")
    else:
        flash("يرجى ملء جميع الحقول", "danger")
        
    return redirect(url_for("dashboard"))

@app.route("/delete_admin/<int:admin_id>", methods=["POST"])
def delete_admin(admin_id):
    if not check_admin():
        return redirect(url_for("login"))
        
    admin = query_db("SELECT username FROM admins WHERE id=%s", (admin_id,), fetchone=True)
    admin_user = session.get("username", "Admin")
    
    if admin and admin["username"] == "TwvxCheat":
        flash("لا يمكنك حذف حساب الأدمن الرئيسي!", "danger")
    else:
        query_db("DELETE FROM admins WHERE id=%s", (admin_id,), commit=True)
        log_action("حذف أدمن", f"قام المشرف {admin_user} بحذف حساب الأدمن ({admin['username'] if admin else admin_id})")
        flash("تم حذف حساب الأدمن بنجاح", "success")
        
    return redirect(url_for("dashboard"))

@app.route("/generate_key", methods=["GET", "POST"])
def generate_key():
    if not check_admin():
        return redirect(url_for("login"))
    
    if request.method == "POST":
        try:
            key_type = request.form.get("key_type", "basic") or "basic"
            duration_days = int(request.form.get("duration_days", 30))
            max_devices = int(request.form.get("max_devices", 1))
            admin_user = session.get("username", "Admin")
            
            key_code = f"TWVX-{key_type.upper()}-" + secrets.token_hex(4).upper()
            
            query_db(
                "INSERT INTO keys (key_code, key_type, created_by, duration_days, max_devices, status) VALUES (%s, %s, %s, %s, %s, 'active')",
                (key_code, key_type, admin_user, duration_days, max_devices),
                commit=True
            )
            log_action("توليد مفتاح", f"قام المشرف {admin_user} بتوليد المفتاح {key_code} ({key_type.upper()}) لمدة {duration_days} يوم")
            flash("تم توليد المفتاح بنجاح!", "success")
        except Exception as e:
            flash(f"خطأ أثناء التوليد: {str(e)}", "danger")
            
    return redirect(url_for("keys_page"))

@app.route("/freeze_key/<int:key_id>", methods=["POST"])
def freeze_key(key_id):
    if not check_admin():
        return redirect(url_for("login"))
        
    key_data = query_db("SELECT * FROM keys WHERE id=%s", (key_id,), fetchone=True)
    if not key_data:
        flash("المفتاح غير موجود", "danger")
        return redirect(url_for("keys_page"))
        
    now = datetime.now()
    is_frozen = key_data.get("is_frozen", 0)
    admin_user = session.get("username", "Admin")
    
    if is_frozen:
        frozen_at_str = key_data.get("frozen_at")
        expires_at_str = key_data.get("expires_at")
        new_expires_at_str = expires_at_str
        
        if frozen_at_str and expires_at_str:
            try:
                frozen_at = datetime.strptime(str(frozen_at_str)[:19], "%Y-%m-%d %H:%M:%S")
                expires_at = datetime.strptime(str(expires_at_str)[:19], "%Y-%m-%d %H:%M:%S")
                freeze_duration = now - frozen_at
                new_expires_at = expires_at + freeze_duration
                new_expires_at_str = new_expires_at.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
                
        query_db(
            "UPDATE keys SET is_frozen=0, frozen_at=NULL, status='active', expires_at=%s WHERE id=%s",
            (new_expires_at_str, key_id),
            commit=True
        )
        log_action("إلغاء تجميد مفتاح", f"قام المشرف {admin_user} بفك تجميد المفتاح {key_data['key_code']}")
        flash("تم إلغاء تجميد المفتاح بنجاح 🟢", "success")
    else:
        if key_data.get("status") == "expired":
            flash("لا يمكن تجميد مفتاح منتهي الصلاحية", "warning")
            return redirect(url_for("keys_page"))
            
        query_db(
            "UPDATE keys SET is_frozen=1, frozen_at=%s, status='frozen' WHERE id=%s",
            (now.strftime("%Y-%m-%d %H:%M:%S"), key_id),
            commit=True
        )
        log_action("تجميد مفتاح", f"قام المشرف {admin_user} بتجميد المفتاح {key_data['key_code']}")
        flash("تم تجميد المفتاح بنجاح ❄️", "warning")
        
    return redirect(url_for("keys_page"))

@app.route("/reset_hwid/<int:key_id>", methods=["GET", "POST"])
def reset_hwid(key_id):
    if not check_admin():
        return redirect(url_for("login"))
    
    key_data = query_db("SELECT key_code FROM keys WHERE id=%s", (key_id,), fetchone=True)
    admin_user = session.get("username", "Admin")
    
    query_db("UPDATE keys SET hwid=NULL WHERE id=%s", (key_id,), commit=True)
    if key_data:
        log_action("إعادة ضبط HWID", f"قام المشرف {admin_user} بمسح الأجهزة للمفتاح {key_data['key_code']}")
        
    flash("تم مسح الأجهزة المسجلة للمفتاح", "success")
    return redirect(url_for("keys_page"))

@app.route("/delete_key/<int:key_id>", methods=["GET", "POST"])
def delete_key(key_id):
    if not check_admin():
        return redirect(url_for("login"))
        
    key_data = query_db("SELECT key_code FROM keys WHERE id=%s", (key_id,), fetchone=True)
    admin_user = session.get("username", "Admin")
    
    query_db("DELETE FROM keys WHERE id=%s", (key_id,), commit=True)
    if key_data:
        log_action("حذف مفتاح", f"قام المشرف {admin_user} بحذف المفتاح {key_data['key_code']}")
        
    flash("تم حذف المفتاح", "success")
    return redirect(url_for("keys_page"))

# --- API التفعيل والمصادقة المطور مع نموذج فحص للمتصفح ---
@app.route("/api/verify", methods=["GET", "POST"])
def api_verify():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form or {}
        key_code = data.get("key", "").strip()
        hwid = data.get("hwid", "").strip()
    else:
        key_code = request.args.get("key", "").strip()
        hwid = request.args.get("hwid", "").strip()

    is_browser = "text/html" in request.headers.get("Accept", "") and not request.headers.get("X-Loader")

    # واجهة إدخال البيانات مباشرة عند فتح الرابط من المتصفح بدون برامترات
    if is_browser and (not key_code or not hwid):
        return """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TwvxCheat - فحص الاشتراك</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700;900&display=swap" rel="stylesheet">
            <style>
                body {
                    background: #070a12;
                    color: #ffffff;
                    font-family: 'Tajawal', sans-serif;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 15px;
                    margin: 0;
                }
                .search-card {
                    background: rgba(15, 23, 42, 0.85);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(16px);
                    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
                    max-width: 420px;
                    width: 100%;
                    padding: 30px 24px;
                }
                .form-control {
                    background: rgba(3, 7, 18, 0.8) !important;
                    border: 1px solid #374151 !important;
                    color: #fff !important;
                    border-radius: 10px;
                    padding: 12px;
                }
                .form-control:focus {
                    border-color: #38bdf8 !important;
                    box-shadow: 0 0 10px rgba(56, 189, 248, 0.3) !important;
                }
                .btn-check-key {
                    background: linear-gradient(135deg, #2563eb, #38bdf8);
                    color: #fff;
                    font-weight: 700;
                    border: none;
                    border-radius: 10px;
                    padding: 12px;
                    width: 100%;
                    transition: 0.3s;
                }
                .btn-check-key:hover {
                    opacity: 0.9;
                    transform: translateY(-2px);
                }
            </style>
        </head>
        <body>
            <div class="search-card text-center">
                <div class="mb-4">
                    <i class="fa-solid fa-shield-halved text-info fs-1 mb-2"></i>
                    <h4 class="fw-bold">فحص حالة الاشتراك</h4>
                    <p class="text-muted small">أدخل المفتاح ومعرف الجهاز (HWID) للتحقق</p>
                </div>
                <form action="/api/verify" method="GET">
                    <div class="mb-3 text-start">
                        <label class="form-label small text-muted">رمز المفتاح (Key)</label>
                        <input type="text" name="key" class="form-control" placeholder="TWVX-BASIC-XXXX" required>
                    </div>
                    <div class="mb-4 text-start">
                        <label class="form-label small text-muted">معرف الجهاز (HWID)</label>
                        <input type="text" name="hwid" class="form-control" placeholder="HWID-12345" required>
                    </div>
                    <button type="submit" class="btn btn-check-key">
                        <i class="fa-solid fa-magnifying-glass me-1"></i> فحص الآن
                    </button>
                </form>
            </div>
        </body>
        </html>
        """, 200

    def render_api_response(status_str, http_code=200):
        if is_browser:
            is_valid = status_str.startswith("VALID")
            is_frozen = "FROZEN" in status_str
            is_expired = "EXPIRED" in status_str
            
            key_type = "BASIC"
            days_left = "-"
            devices = "-"
            signature = "-"

            if is_valid:
                parts = status_str.split("|")
                if len(parts) >= 5:
                    key_type = parts[1]
                    days_left = parts[2].replace("_DAYS", " يوم")
                    devices = parts[3]
                    signature = parts[4].replace("SIG:", "")

            if is_valid:
                title = "الاشتراك فعال ونشط"
                theme_color = "#22c55e"
                icon_class = "fa-circle-check"
            elif is_frozen:
                title = "الاشتراك مجمد مؤقتاً"
                theme_color = "#38bdf8"
                icon_class = "fa-snowflake"
            elif is_expired:
                title = "الاشتراك منتهي الصلاحية"
                theme_color = "#f59e0b"
                icon_class = "fa-clock"
            else:
                title = "تم رفض الوصول / المفتاح غير صالح"
                theme_color = "#ef4444"
                icon_class = "fa-circle-xmark"

            html_ui = f"""
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>TwvxCheat - Verification Status</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
                <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700;900&display=swap" rel="stylesheet">
                <style>
                    body {{
                        background: #070a12;
                        color: #ffffff;
                        font-family: 'Tajawal', sans-serif;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 15px;
                        margin: 0;
                    }}
                    .status-card {{
                        background: rgba(15, 23, 42, 0.85);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-top: 4px solid {theme_color};
                        border-radius: 20px;
                        backdrop-filter: blur(16px);
                        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6), 0 0 20px {theme_color}22;
                        max-width: 440px;
                        width: 100%;
                        padding: 28px 22px;
                    }}
                    .status-header {{
                        color: {theme_color};
                        font-weight: 800;
                        font-size: 1.35rem;
                        margin-bottom: 22px;
                    }}
                    .info-box {{
                        background: rgba(3, 7, 18, 0.6);
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-radius: 12px;
                        padding: 12px;
                        text-align: center;
                    }}
                    .info-label {{
                        font-size: 0.75rem;
                        color: #94a3b8;
                        margin-bottom: 4px;
                    }}
                    .info-value {{
                        font-weight: 700;
                        font-size: 1rem;
                        color: #f8fafc;
                    }}
                    .sig-box {{
                        background: #030712;
                        border: 1px dashed {theme_color}66;
                        border-radius: 10px;
                        padding: 10px;
                        font-family: monospace;
                        color: {theme_color};
                        font-size: 0.9rem;
                        letter-spacing: 1px;
                    }}
                    .footer-text {{
                        font-size: 0.75rem;
                        color: #64748b;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="status-card text-center">
                    <div class="status-header d-flex align-items-center justify-content-center gap-2">
                        <i class="fa-solid {icon_class} fs-3"></i>
                        <span>{title}</span>
                    </div>

                    {" " if not is_valid else f'''
                    <div class="row g-2 mb-3">
                        <div class="col-6">
                            <div class="info-box">
                                <div class="info-label"><i class="fa-solid fa-crown me-1 text-warning"></i> نوع الاشتراك</div>
                                <div class="info-value text-warning">{key_type}</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="info-box">
                                <div class="info-label"><i class="fa-solid fa-hourglass-half me-1 text-info"></i> المدة المتبقية</div>
                                <div class="info-value text-info">{days_left}</div>
                            </div>
                        </div>
                        <div class="col-12">
                            <div class="info-box">
                                <div class="info-label"><i class="fa-solid fa-desktop me-1 text-primary"></i> الأجهزة المسجلة</div>
                                <div class="info-value text-light">{devices}</div>
                            </div>
                        </div>
                    </div>

                    <div class="sig-box d-flex justify-content-between align-items-center">
                        <span id="sigText"><i class="fa-solid fa-shield-halved me-1"></i> SIG: {signature}</span>
                        <button class="btn btn-sm text-light p-0 border-0" onclick="copySig('{signature}')" title="نسخ">
                            <i class="fa-regular fa-copy text-muted ms-2" id="copyIcon"></i>
                        </button>
                    </div>
                    '''}

                    <div class="mt-3">
                        <a href="/api/verify" class="btn btn-sm btn-outline-secondary w-100 rounded-3">فحص مفتاح آخر</a>
                    </div>

                    <div class="footer-text">
                        <span>واجهة برمجة تطبيقات الأمان TWVXCHEAT</span>
                    </div>
                </div>

                <script>
                    function copySig(text) {{
                        navigator.clipboard.writeText(text);
                        const icon = document.getElementById('copyIcon');
                        icon.className = 'fa-solid fa-check text-success ms-2';
                        setTimeout(() => {{ icon.className = 'fa-regular fa-copy text-muted ms-2'; }}, 1500);
                    }}
                </script>
            </body>
            </html>
            """
            return html_ui, http_code
        return status_str, http_code

    if not key_code or not hwid:
        return render_api_response("INVALID:MISSING_DATA", 400)

    key_data = query_db("SELECT * FROM keys WHERE key_code=%s", (key_code,), fetchone=True)
    if not key_data:
        return render_api_response("INVALID:NOT_FOUND", 404)

    if key_data.get("status") == "banned":
        return render_api_response("INVALID:BANNED", 403)

    if key_data.get("is_frozen") == 1 or key_data.get("status") == "frozen":
        return render_api_response("INVALID:FROZEN", 403)

    now = datetime.now()

    if key_data.get("expires_at"):
        exp_date = datetime.strptime(str(key_data["expires_at"])[:19], "%Y-%m-%d %H:%M:%S")
        if now > exp_date:
            query_db("UPDATE keys SET status='expired' WHERE id=%s", (key_data["id"],), commit=True)
            return render_api_response("INVALID:EXPIRED", 403)

    registered_hwids = [h for h in (key_data.get("hwid") or "").split(",") if h]
    max_devices = key_data.get("max_devices", 1)

    if hwid not in registered_hwids:
        if len(registered_hwids) >= max_devices:
            return render_api_response("INVALID:MAX_DEVICES_REACHED", 403)

        registered_hwids.append(hwid)
        new_hwid_str = ",".join(registered_hwids)

        if not key_data.get("activated_at"):
            duration = key_data.get("duration_days", 30)
            expires_at = now + timedelta(days=duration)
            query_db(
                "UPDATE keys SET hwid=%s, activated_at=%s, expires_at=%s WHERE id=%s",
                (new_hwid_str, now.strftime("%Y-%m-%d %H:%M:%S"), expires_at.strftime("%Y-%m-%d %H:%M:%S"), key_data["id"]),
                commit=True
            )
            days_left = duration
        else:
            query_db("UPDATE keys SET hwid=%s WHERE id=%s", (new_hwid_str, key_data["id"]), commit=True)
            exp_date = datetime.strptime(str(key_data["expires_at"])[:19], "%Y-%m-%d %H:%M:%S")
            days_left = max(0, (exp_date - now).days)
    else:
        exp_date = datetime.strptime(str(key_data["expires_at"])[:19], "%Y-%m-%d %H:%M:%S")
        days_left = max(0, (exp_date - now).days)

    log_action("استخدام مفتاح", f"زبون استخدم المفتاح {key_code} من جهاز HWID ({hwid})")

    secret_salt = "TWVX_SECRET_PROTECTION_2026"
    raw_sig = f"{key_code}:{hwid}:{secret_salt}"
    signature = hashlib.md5(raw_sig.encode()).hexdigest()[:10].upper()

    key_type = (key_data.get("key_type") or "basic").upper()
    response_payload = f"VALID|{key_type}|{days_left}_DAYS|{len(registered_hwids)}/{max_devices}|SIG:{signature}"

    return render_api_response(response_payload, 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
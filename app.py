import os
import secrets
import sqlite3
import pymysql
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "twvx_cheat_secret_key_12345")
DB_FILE = "twvx_db.db"

# --- نظام الاتصال المزدوج (MySQL / SQLite Fallback) ---
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

# --- تهيئة الجداول ---
def init_db():
    conn, db_type = get_db()
    cursor = conn.cursor()
    
    if db_type == "sqlite":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_code TEXT UNIQUE NOT NULL,
                key_type TEXT DEFAULT 'basic',
                status TEXT DEFAULT 'active',
                used_by TEXT DEFAULT '-',
                duration_days INTEGER DEFAULT 30,
                max_devices INTEGER DEFAULT 1,
                hwid TEXT DEFAULT NULL,
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
        conn.commit()
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `keys` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `key_code` VARCHAR(255) UNIQUE NOT NULL,
                `key_type` VARCHAR(50) DEFAULT 'basic',
                `status` VARCHAR(50) DEFAULT 'active',
                `used_by` VARCHAR(255) DEFAULT '-',
                `duration_days` INT DEFAULT 30,
                `max_devices` INT DEFAULT 1,
                `hwid` TEXT DEFAULT NULL,
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
    conn.close()

init_db()

def check_admin():
    return session.get("logged_in") is True

# --- المسارات ---

@app.route("/")
def index():
    if check_admin():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == "TwvxCheat" and password == "Twvx1":
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
            
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard", methods=["GET", "POST"])
@app.route("/keys", methods=["GET", "POST"])
@app.route("/keys_page", methods=["GET", "POST"], endpoint="keys_page")
def dashboard():
    if not check_admin():
        return redirect(url_for("login"))
    
    keys_list = query_db("SELECT * FROM keys ORDER BY id DESC") or []
    
    total_keys = len(keys_list)
    active_keys = sum(1 for k in keys_list if k.get("status") == "active")
    expired_keys = sum(1 for k in keys_list if k.get("status") == "expired")
    banned_keys = sum(1 for k in keys_list if k.get("status") == "banned")
    used_keys = sum(1 for k in keys_list if k.get("hwid"))

    return render_template(
        "dashboard.html", 
        keys=keys_list,
        total_keys=total_keys,
        active_keys=active_keys,
        expired_keys=expired_keys,
        banned_keys=banned_keys,
        used_keys=used_keys
    )

@app.route("/generate_key", methods=["GET", "POST"])
def generate_key():
    if not check_admin():
        return redirect(url_for("login"))
    
    if request.method == "POST":
        try:
            key_type = request.form.get("key_type", "basic") or "basic"
            duration_days = int(request.form.get("duration_days", 30))
            max_devices = int(request.form.get("max_devices", 1))
            
            key_code = f"TWVX-{key_type.upper()}-" + secrets.token_hex(4).upper()
            
            query_db(
                "INSERT INTO keys (key_code, key_type, duration_days, max_devices, status) VALUES (%s, %s, %s, %s, 'active')",
                (key_code, key_type, duration_days, max_devices),
                commit=True
            )
            flash("تم توليد المفتاح بنجاح!", "success")
        except Exception as e:
            flash(f"خطأ أثناء التوليد: {str(e)}", "danger")
            
    return redirect(url_for("keys_page"))

@app.route("/reset_hwid/<int:key_id>", methods=["GET", "POST"])
def reset_hwid(key_id):
    if not check_admin():
        return redirect(url_for("login"))
    query_db("UPDATE keys SET hwid=NULL WHERE id=%s", (key_id,), commit=True)
    flash("تم مسح الأجهزة المسجلة للمفتاح", "success")
    return redirect(url_for("keys_page"))

@app.route("/delete_key/<int:key_id>", methods=["GET", "POST"])
def delete_key(key_id):
    if not check_admin():
        return redirect(url_for("login"))
    query_db("DELETE FROM keys WHERE id=%s", (key_id,), commit=True)
    flash("تم حذف المفتاح", "success")
    return redirect(url_for("keys_page"))

# --- API للتحقق من الكي ---
@app.route("/api/verify", methods=["POST"])
def api_verify():
    data = request.get_json() or {}
    key_code = data.get("key")
    hwid = data.get("hwid")
    
    if not key_code or not hwid:
        return jsonify({"status": "error", "message": "المفتاح وبصمة الجهاز مطلوبة"}), 400
        
    key_data = query_db("SELECT * FROM keys WHERE key_code=%s", (key_code,), fetchone=True)
    if not key_data:
        return jsonify({"status": "error", "message": "المفتاح غير موجود"}), 404
        
    if key_data["status"] == "banned":
        return jsonify({"status": "error", "message": "هذا المفتاح محظور"}), 403
        
    now = datetime.now()
    if key_data["expires_at"] and now > datetime.strptime(str(key_data["expires_at"])[:19], "%Y-%m-%d %H:%M:%S"):
        query_db("UPDATE keys SET status='expired' WHERE id=%s", (key_data["id"],), commit=True)
        return jsonify({"status": "error", "message": "المفتاح منتهي الصلاحية"}), 403
        
    registered_hwids = key_data["hwid"].split(",") if key_data["hwid"] else []
    max_devices = key_data.get("max_devices", 1)
    
    if hwid not in registered_hwids:
        if len(registered_hwids) >= max_devices:
            return jsonify({"status": "error", "message": "MAX_DEVICES_REACHED"}), 403
        
        registered_hwids.append(hwid)
        new_hwid_str = ",".join(registered_hwids)
        
        if not key_data["activated_at"]:
            expires_at = now + timedelta(days=key_data["duration_days"])
            query_db(
                "UPDATE keys SET hwid=%s, activated_at=%s, expires_at=%s WHERE id=%s",
                (new_hwid_str, now.strftime("%Y-%m-%d %H:%M:%S"), expires_at.strftime("%Y-%m-%d %H:%M:%S"), key_data["id"]),
                commit=True
            )
        else:
            query_db("UPDATE keys SET hwid=%s WHERE id=%s", (new_hwid_str, key_data["id"]), commit=True)

    return jsonify({
        "status": "success",
        "message": "تم التفعيل بنجاح",
        "key_type": key_data["key_type"],
        "max_devices": max_devices,
        "current_devices": len(registered_hwids)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
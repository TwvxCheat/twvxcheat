import os
import secrets
import pymysql
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "twvx_cheat_secret_key_12345")

# --- الاتصال بقاعدة البيانات ---
def connect_db():
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "twvx_db"),
            port=int(os.environ.get("DB_PORT", 3306)),
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn, None
    except Exception as e:
        return None, str(e)

# --- تهيئة وتحديث قاعدة البيانات تلقائياً ---
def init_db():
    conn, err = connect_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
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
                
                cols = [
                    ("key_type", "VARCHAR(50) DEFAULT 'basic'"),
                    ("used_by", "VARCHAR(255) DEFAULT '-'"),
                    ("duration_days", "INT DEFAULT 30"),
                    ("max_devices", "INT DEFAULT 1"),
                    ("activated_at", "DATETIME DEFAULT NULL"),
                    ("expires_at", "DATETIME DEFAULT NULL")
                ]
                for col_name, col_type in cols:
                    try:
                        cur.execute(f"ALTER TABLE `keys` ADD COLUMN `{col_name}` {col_type};")
                    except Exception:
                        pass

                try:
                    cur.execute("ALTER TABLE `keys` ADD COLUMN `hwid` TEXT DEFAULT NULL;")
                except Exception:
                    try:
                        cur.execute("ALTER TABLE `keys` MODIFY COLUMN `hwid` TEXT DEFAULT NULL;")
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
                
                cur.execute("DELETE FROM admins;")
                cur.execute("INSERT INTO admins (username, password) VALUES (%s, %s);", ("TwvxCheat", "Twvx1"))
            conn.close()
        except Exception as e:
            print("DB Init Error:", e)

init_db()

def check_admin():
    return session.get("logged_in") is True

# --- المسارات (Routes) ---

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
        
        # تحقق مباشر من بيانات الأدمن الرئيسي
        if username == "TwvxCheat" and password == "Twvx1":
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
            
        conn, _ = connect_db()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admins WHERE username=%s AND password=%s", (username, password))
                admin = cur.fetchone()
            conn.close()
            if admin:
                session["logged_in"] = True
                session["username"] = username
                return redirect(url_for("dashboard"))
                
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# تم السماح بـ GET و POST لحل مشكلة 405
@app.route("/dashboard", methods=["GET", "POST"])
@app.route("/keys", methods=["GET", "POST"])
@app.route("/keys_page", methods=["GET", "POST"], endpoint="keys_page")
def dashboard():
    if not check_admin():
        return redirect(url_for("login"))
    
    conn, err = connect_db()
    keys_list = []
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM `keys` ORDER BY id DESC")
            keys_list = cur.fetchall()
        conn.close()
    
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

@app.route("/generate_key", methods=["POST"])
def generate_key():
    if not check_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    key_type = request.form.get("key_type", "basic")
    duration_days = int(request.form.get("duration_days", 30))
    max_devices = int(request.form.get("max_devices", 1))
    
    key_code = f"TWVX-{key_type.upper()}-" + secrets.token_hex(4).upper()
    
    conn, err = connect_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO `keys` (key_code, key_type, duration_days, max_devices, status)
                VALUES (%s, %s, %s, %s, 'active')
            """, (key_code, key_type, duration_days, max_devices))
        conn.close()
        flash("تم توليد المفتاح بنجاح!", "success")
    else:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        
    return redirect(url_for("keys_page"))

@app.route("/reset_hwid/<int:key_id>", methods=["POST"])
def reset_hwid(key_id):
    if not check_admin():
        return redirect(url_for("login"))
    conn, _ = connect_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE `keys` SET hwid=NULL WHERE id=%s", (key_id,))
        conn.close()
        flash("تم مسح الأجهزة المسجلة للمفتاح بنجاح", "success")
    return redirect(url_for("keys_page"))

@app.route("/delete_key/<int:key_id>", methods=["POST"])
def delete_key(key_id):
    if not check_admin():
        return redirect(url_for("login"))
    conn, _ = connect_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `keys` WHERE id=%s", (key_id,))
        conn.close()
        flash("تم حذف المفتاح", "success")
    return redirect(url_for("keys_page"))

# --- API للتحقق من الكي من داخل اللعبة / البرنامج ---
@app.route("/api/verify", methods=["POST"])
def api_verify():
    data = request.get_json() or {}
    key_code = data.get("key")
    hwid = data.get("hwid")
    
    if not key_code or not hwid:
        return jsonify({"status": "error", "message": "المفتاح وبصمة الجهاز مطلوبة"}), 400
        
    conn, _ = connect_db()
    if not conn:
        return jsonify({"status": "error", "message": "خطأ في السيرفر"}), 500
        
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM `keys` WHERE key_code=%s", (key_code,))
        key_data = cur.fetchone()
        
        if not key_data:
            conn.close()
            return jsonify({"status": "error", "message": "المفتاح غير موجود"}), 404
            
        if key_data["status"] == "banned":
            conn.close()
            return jsonify({"status": "error", "message": "هذا المفتاح محظور"}), 403
            
        now = datetime.now()
        if key_data["expires_at"] and now > key_data["expires_at"]:
            cur.execute("UPDATE `keys` SET status='expired' WHERE id=%s", (key_data["id"],))
            conn.close()
            return jsonify({"status": "error", "message": "المفتاح منتهي الصلاحية"}), 403
            
        registered_hwids = key_data["hwid"].split(",") if key_data["hwid"] else []
        max_devices = key_data.get("max_devices", 1)
        
        if hwid not in registered_hwids:
            if len(registered_hwids) >= max_devices:
                conn.close()
                return jsonify({"status": "error", "message": "MAX_DEVICES_REACHED"}), 403
            
            registered_hwids.append(hwid)
            new_hwid_str = ",".join(registered_hwids)
            
            if not key_data["activated_at"]:
                expires_at = now + timedelta(days=key_data["duration_days"])
                cur.execute("""
                    UPDATE `keys` 
                    SET hwid=%s, activated_at=%s, expires_at=%s 
                    WHERE id=%s
                """, (new_hwid_str, now, expires_at, key_data["id"]))
            else:
                cur.execute("UPDATE `keys` SET hwid=%s WHERE id=%s", (new_hwid_str, key_data["id"]))

    conn.close()
    return jsonify({
        "status": "success",
        "message": "تم التفعيل بنجاح",
        "key_type": key_data["key_type"],
        "max_devices": max_devices,
        "current_devices": len(registered_hwids)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
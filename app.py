from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import random
import string
import psycopg2

app = Flask(__name__)

# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= ADMIN =================
ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

# ================= DB CONNECTION =================
def connect_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment variables")
    
    # إجبار الاتصال الآمن SSL المطلوب على خوادم Render
    if "sslmode" not in db_url:
        if "?" in db_url:
            db_url += "&sslmode=require"
        else:
            db_url += "?sslmode=require"
            
    return psycopg2.connect(db_url)

# ================= INIT DB & MIGRATION =================
def init_db():
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # إنشاء الجدول إذا لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id SERIAL PRIMARY KEY,
                key_code TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # التحقق وتحديث اسم العمود من key إلى key_code تلقائياً إن وجد
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='keys' AND column_name='key_code') THEN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='keys' AND column_name='key') THEN
                        ALTER TABLE keys RENAME COLUMN key TO key_code;
                    ELSE
                        ALTER TABLE keys ADD COLUMN key_code TEXT UNIQUE;
                    END IF;
                END IF;
            END $$;
        """)
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

# تشغيل التهيئة عند بدء السيرفر
try:
    init_db()
except Exception as e:
    print("Failed to run init_db:", e)

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

@app.route("/dashboard")
def dashboard():
    if not check_admin():
        return redirect("/login")
    keys = []
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM keys ORDER BY id DESC")
        keys = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"خطأ في الاتصال بقاعدة البيانات: {e}", "danger")
    return render_template("dashboard.html", keys=keys)

@app.route("/generate", methods=["GET", "POST"])
def generate():
    if not check_admin():
        return redirect("/login")
    if request.method == "POST":
        new_key = "TWVX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        try:
            conn = connect_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO keys (key_code, status) VALUES (%s, %s)", (new_key, 'active'))
            conn.commit()
            cur.close()
            conn.close()
            flash(f"تم إنشاء المفتاح: {new_key}", "success")
        except Exception as e:
            flash(f"خطأ عند إنشاء المفتاح: {e}", "danger")
        return redirect("/dashboard")
    return render_template("generate.html")

@app.route("/delete/<int:key_id>")
def delete_key(key_id):
    if not check_admin():
        return redirect("/login")
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM keys WHERE id = %s", (key_id,))
        conn.commit()
        cur.close()
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
    keys = []
    try:
        conn = connect_db()
        cur = conn.cursor()
        if q == "":
            cur.execute("SELECT * FROM keys ORDER BY id DESC")
        else:
            cur.execute("SELECT * FROM keys WHERE key_code LIKE %s", ('%' + q + '%',))
        keys = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"خطأ أثناء البحث: {e}", "danger")
    return render_template("dashboard.html", keys=keys)

# ================= VERIFY API (C++) =================
@app.route("/verify", methods=["GET", "POST"])
def verify():
    key = request.args.get("key") or request.form.get("key", "")
    if not key:
        return "INVALID", 200, {'Content-Type': 'text/plain'}
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT status FROM keys WHERE key_code = %s", (key,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and (result[0] == 'active' or result[0] == 'valid'):
            return "VALID", 200, {'Content-Type': 'text/plain'}
        else:
            return "INVALID", 200, {'Content-Type': 'text/plain'}
    except Exception:
        return "ERROR", 500, {'Content-Type': 'text/plain'}

# ================= RUN =================
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import random
import string
from datetime import datetime, timedelta
import psycopg2

app = Flask(__name__)

# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= ADMIN =================
ADMIN_USER = "TwvxCheat"
ADMIN_PASS = "Twvx1"

# ================= DB =================
def connect_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

# ================= INIT DB =================
def init_db():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id SERIAL PRIMARY KEY,
                key_code TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

def check_admin():
    return session.get("logged_in")

# ================= VERIFY (C++ API) =================
@app.route("/verify", methods=["GET", "POST"])
def verify():
    key = request.args.get("key") or request.form.get("key", "")
    if not key:
        return "INVALID", 200, {'Content-Type': 'text/plain'}
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # البحث بـ key_code
        cur.execute("SELECT status FROM keys WHERE key_code = %s", (key,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result and (result[0] == 'active' or result[0] == 'valid'):
            return "VALID", 200, {'Content-Type': 'text/plain'}
        else:
            return "INVALID", 200, {'Content-Type': 'text/plain'}
            
    except Exception as e:
        return "ERROR", 500, {'Content-Type': 'text/plain'}

# ================= SEARCH =================
@app.route("/search")
def search():
    if not check_admin():
        return redirect("/login")
        
    q = request.args.get("q", "")
    conn = connect_db()
    cur = conn.cursor()
    
    if q.strip() == "":
        cur.execute("SELECT * FROM keys ORDER BY id DESC")
    else:
        cur.execute("SELECT * FROM keys WHERE key_code LIKE %s", ('%' + q + '%',))
        
    keys = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("dashboard.html", keys=keys)

# ================= RUN =================
application = app

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
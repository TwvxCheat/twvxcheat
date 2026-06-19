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
            key TEXT,
            lim INTEGER,
            used INTEGER,
            expire TEXT,
            status TEXT
        )
        """)

        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print("❌ DB init error:", e)

init_db()

# ================= ADMIN CHECK =================
def check_admin():
    return session.get("admin")

# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("pass")

        if user == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("dashboard"))

        flash("Wrong credentials ❌", "danger")

    return render_template("login.html")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= DASHBOARD =================
@app.route("/")
def dashboard():
    if not check_admin():
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM keys ORDER BY id DESC")
    keys = cur.fetchall()

    conn.close()

    return render_template("dashboard.html", keys=keys)

# ================= CREATE KEY =================
@app.route("/create", methods=["POST"])
def create():
    if not check_admin():
        return redirect("/login")

    limit = request.form.get("limit")
    days = request.form.get("days")

    if not limit or not days:
        flash("Fill all fields ❌", "danger")
        return redirect(url_for("dashboard"))

    key = "KEY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    expire = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO keys (key, lim, used, expire, status)
        VALUES (%s, %s, 0, %s, 'active')
    """, (key, int(limit), expire))

    conn.commit()
    conn.close()

    flash("Key generated ✅", "success")
    return redirect(url_for("dashboard"))

# ================= DELETE KEY =================
@app.route("/delete/<int:id>")
def delete(id):
    if not check_admin():
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM keys WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    flash("Key deleted 🗑️", "warning")
    return redirect(url_for("dashboard"))

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
        cur.execute("SELECT * FROM keys WHERE key LIKE %s", ('%' + q + '%',))

    keys = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", keys=keys)

# ================= RUN =================
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
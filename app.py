from flask import Flask, render_template, request, redirect, session, g, url_for, current_app
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import waitress
import os

# --- DATABASE CONFIG ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")  # store DB in project root

# --- FLASK CONFIG ---
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "replace_this_with_real_secret")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# --- DATABASE HELPERS ---
def get_db():
    if "db" not in g:
        print("📁 Connecting to database:", os.path.abspath(DB_PATH))  # <-- debug print
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# --- ROUTES ---
@app.route("/")
def index():
    return render_template("index.html", username=session.get("username"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        hostel = request.form.get("hostel", "").strip()
        phone = request.form.get("phone", "").strip()

        if not username or not password:
            return render_template("signup.html", error="Missing username or password")

        db = get_db()
        # check existing user
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return render_template("signup.html", error="Username already exists")

        try:
            password_hash = generate_password_hash(password)
            db.execute(
                "INSERT INTO users (username, password_hash, hostel, phone) VALUES (?, ?, ?, ?)",
                (username, password_hash, hostel, phone)
            )
            db.commit()
        except Exception as e:
            print("❌ DB Insert Error:", e)
            return render_template("signup.html", error="Database error: " + str(e))

        session["username"] = username
        return redirect("/signin")

    return render_template("signup.html")

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("signin.html", error="Missing username or password")

        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return render_template("signin.html", error="Invalid credentials")

        session["username"] = username
        session["user_id"] = row["id"]
        session["hostel"] = row["hostel"]

        return redirect("/dashboard")

    return render_template("signin.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("signin"))
    return render_template("dashboard.html", username=session["username"])

@app.route('/browseItems')
def browse_items():
    return render_template('browseItems.html', username=session["username"])

@app.route('/swapRequests')
def swap_requests():
    return render_template('swapRequests.html')

@app.route('/savedItems')
def saved_items():
    return render_template('savedItems.html')


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("signin"))

    user_id = session["user_id"]

    db = get_db()

     # Active listings
    active_listings = db.execute("""
        SELECT *
        FROM items
        WHERE owner_id = ?
          AND is_active = 1
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    # TEMPORARY placeholders (tables not implemented yet)
    swap_history = []
    saved_items = []

    return render_template(
        "profile.html",
        username=session["username"],
        active_listings=active_listings,
        swap_history=swap_history,
        saved_items=saved_items
    )



@app.route('/myListings')
def my_listings():
    return render_template('Listings.html', username=session["username"])

@app.route('/notifications')
def notifications():
    return render_template('notifications.html', username=session["username"])


@app.route('/settings')
def settings():
    return render_template('settings.html')



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    from waitress import serve
    if os.getenv('FLASK_ENV') == 'production':
        serve(app, host="0.0.0.0", port=8080)  # Production server
    else:
        app.run(debug=True, host="0.0.0.0", port=8080)  # Development server

# how to rubn... python -m flask run
from flask import Flask, render_template, request, redirect, session, g, url_for, current_app, session, jsonify, flash
from werkzeug.utils import secure_filename
from flask_session import Session
from datetime import datetime, timezone
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

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- DATABASE HELPERS ---
def get_db():
    if "db" not in g:
        print("📁 Connecting to database:", os.path.abspath(DB_PATH))  # <-- debug print
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def time_ago(dt):
    if isinstance(dt, str):
        dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)} minutes ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} hours ago"
    else:
        return f"{int(seconds // 86400)} days ago"


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

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    db = get_db()
    user_id = session['user_id']

    # Compute stats from existing tables
    active_offers = db.execute(
        "SELECT COUNT(*) FROM items WHERE owner_id = ? AND is_active = 1",
        (user_id,)
    ).fetchone()[0]

    total_views = db.execute(
        "SELECT COALESCE(SUM(views), 0) FROM items WHERE owner_id = ?",
        (user_id,)
    ).fetchone()[0]

    stats = {
        "active_offers": active_offers,
        "pending_requests": 11,     # placeholder
        "completed_swaps": 11,      # placeholder
        "matches": 0,              # placeholder
        "success_rate": 0,
        "total_attempts": 0
    }

    return render_template(
        "dashboard.html",
        username=session["username"],
        stats=stats,
        swap_requests=[],
        recent_activity=[],
        matches=[]
    )

@app.route('/swapRequests')
def swap_requests():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    db = get_db()
    user_id = session['user_id']

    # Incoming
    incoming = db.execute("""
        SELECT 
            sr.id,
            sr.message,
            sr.status,
            sr.created_at,
            i.name AS item_name,
            i.image AS item_image,
            u.username AS requester_name,
            u.email AS requester_email,
            u.phone AS requester_phone
        FROM swap_requests sr
        JOIN items i ON sr.item_id = i.id
        JOIN users u ON sr.requester_id = u.id
        WHERE sr.owner_id = :user_id
        ORDER BY sr.created_at DESC
    """, {"user_id": user_id}).fetchall()

    # Outgoing
    outgoing = db.execute("""
        SELECT 
            sr.id,
            sr.message,
            sr.status,
            sr.created_at,
            i.name AS item_name,
            i.image AS item_image,
            u.username AS owner_name,
            u.email AS owner_email,
            u.phone AS owner_phone
        FROM swap_requests sr
        JOIN items i ON sr.item_id = i.id
        JOIN users u ON sr.owner_id = u.id
        WHERE sr.requester_id = :user_id
        ORDER BY sr.created_at DESC
    """, {"user_id": user_id}).fetchall()

    # Add time_ago to each request
    incoming_requests = []
    for r in incoming:
        r = dict(r)
        r['time_ago'] = time_ago(r['created_at'])
        incoming_requests.append(r)

    outgoing_requests = []
    for r in outgoing:
        r = dict(r)
        r['time_ago'] = time_ago(r['created_at'])
        outgoing_requests.append(r)

    incoming_count = sum(1 for r in incoming_requests if r['status'] == 'pending')

    return render_template(
        'swapRequests.html',
        username=session["username"],
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        incoming_count=incoming_count,
        success=request.args.get('success'),
        error=request.args.get('error')
    )

@app.route('/swap/respond/<int:request_id>', methods=['POST'])
def respond_to_swap(request_id):
    if 'user_id' not in session:
        return {"success": False}, 403

    db = get_db()
    user_id = session['user_id']
    data = request.get_json()
    action = data.get("action")

    if action not in ["accepted", "rejected"]:
        return {"success": False}, 400

    # Verify ownership
    swap = db.execute("""
        SELECT id FROM swap_requests
        WHERE id = ? AND owner_id = ?
    """, (request_id, user_id)).fetchone()

    if not swap:
        return {"success": False}, 403

    db.execute("""
        UPDATE swap_requests
        SET status = ?, responded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (action, request_id))

    db.commit()

    return jsonify( success=True,
                   message="Swap accepted successfully." if action == "accepted"
                else "Swap declined.",
        status=action
    )

@app.route("/swap/request/<int:item_id>", methods=["POST"])
def request_swap(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()

    # Get item info
    item = db.execute("""
        SELECT id, owner_id, is_active
        FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:
        return "Item not found", 404

    # Prevent requesting your own item
    if item["owner_id"] == user_id:
        return "You cannot request your own item", 403

    # Prevent requesting unavailable item
    if item["is_active"] != 1:
        return "Item not available", 400

    # Prevent duplicate pending requests
    existing = db.execute("""
        SELECT id FROM swap_requests
        WHERE item_id = ? AND requester_id = ? AND status = 'pending'
    """, (item_id, user_id)).fetchone()

    if existing:
        flash("Request already sent.", "warning")
        return redirect(url_for("item_detail", item_id=item_id))


    # Insert swap request
    db.execute("""
        INSERT INTO swap_requests (item_id, requester_id, owner_id, status)
        VALUES (?, ?, ?, 'pending')
    """, (item_id, user_id, item["owner_id"]))

    db.commit()

    
    flash("Swap request sent successfully.", "success")
    return redirect(url_for("browse_items", item_id=item_id, existing=True))






@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("signin"))

    db = get_db()
    user_id = session["user_id"]

     # Active listings
    active_listings = db.execute("""
        SELECT *
        FROM items
        WHERE owner_id = ?
          AND is_active = 1
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    # TEMPORARY placeholders (tables not implemented yet)
    swap_history = []
    saved_items = db.execute("""
    SELECT 
        items.id,
        items.name,
        items.category,
        items.image,
        users.username AS owner_name
    FROM saved_items
    JOIN items ON saved_items.item_id = items.id
    JOIN users ON items.owner_id = users.id
    WHERE saved_items.user_id = ?
      AND items.is_active = 1
    """, (session['user_id'],)).fetchall()


    return render_template(
        "profile.html",
        username=session["username"],
        active_listings=active_listings,
        swap_history=swap_history,
        saved_items=saved_items
    )

# Change Password Route
@app.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not all([current_password, new_password, confirm_password]):
        return redirect(url_for('profile', error='All fields are required'))
    
    if new_password != confirm_password:
        return redirect(url_for('profile', error='New passwords do not match'))
    
    if len(new_password) < 6:
        return redirect(url_for('profile', error='Password must be at least 6 characters'))
    
    # Verify current password
    db = get_db()
    user = db.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not user or not check_password_hash(user['password'], current_password):
        return redirect(url_for('profile', error='Current password is incorrect'))
    
    # Update password
    hashed_password = generate_password_hash(new_password)
    db.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, session['user_id']))
    db.commit()
    
    return redirect(url_for('profile', success='Password updated successfully'))

# Update Profile Route
@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    hostel = request.form.get('hostel')
    
    # Validate inputs
    if not username or not email:
        return redirect(url_for('profile', error='Username and email are required'))
    
    # Check if username or email already exists (for other users)
    db = get_db()
    existing = db.execute('''
        SELECT id FROM users 
        WHERE (username = ? OR email = ?) AND id != ?
    ''', (username, email, session['user_id'])).fetchone()
    
    if existing:
        return redirect(url_for('profile', error='Username or email already taken'))
    
    # Update profile
    db.execute('''
        UPDATE users 
        SET username = ?, email = ?, phone = ?, hostel = ?
        WHERE id = ?
    ''', (username, email, phone, hostel, session['user_id']))
    db.commit()
    
    # Update session
    session['username'] = username
    session['email'] = email
    session['phone'] = phone
    session['hostel'] = hostel
    
    return redirect(url_for('profile', success='Profile updated successfully'))

# Delete Account Route
@app.route('/delete-account')
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    user_id = session['user_id']
    db = get_db()
    
    # Delete user's images
    items = db.execute('SELECT image FROM items WHERE owner_id = ?', (user_id,)).fetchall()
    for item in items:
        if item['image']:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image']))
            except:
                pass
    
    # Delete all user data (cascading should handle this if set up properly)
    db.execute('DELETE FROM items WHERE owner_id = ?', (user_id,))
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    
    # Clear session
    session.clear()
    
    return redirect(url_for('index'))

# Delete Item Route
@app.route('/delete-item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    db = get_db()
    
    # Get item and verify ownership
    item = db.execute(
    "SELECT * FROM items WHERE id = ?",
    (item_id,)
    ).fetchone()

    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for("profile"))
    
    if item["owner_id"] != session['user_id']:
        flash("You cannot delete this item.", "danger")
        return redirect(url_for("profile"))

    
    # Delete image file if exists
    if item['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image']))
        except:
            pass
    
    # Delete from database
    db.execute('DELETE FROM items WHERE id = ?', (item_id,))
    db.commit()
    
    flash("Item deleted successfully.", "success")
    return redirect(url_for("profile"))



# Browse Items Route
@app.route('/browseItems')
def browse_items():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    # Get search parameters
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', 'newest')
    
    db = get_db()
    
    # Build query
    query = '''
        SELECT items.*, users.username as owner_name, users.hostel 
        FROM items 
        JOIN users ON items.owner_id = users.id 
        WHERE items.is_active = 1
    '''
    params = []
    
    # Add search filter
    if search:
        query += " AND (items.name LIKE ? OR items.description LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    # Add category filter
    if category:
        query += " AND items.category = ?"
        params.append(category)
    
    # Add sorting
    if sort == 'newest':
        query += " ORDER BY items.created_at DESC"
    elif sort == 'oldest':
        query += " ORDER BY items.created_at ASC"
    elif sort == 'popular':
        query += " ORDER BY items.views DESC"
    
    items = db.execute(query, params).fetchall()
    
    return render_template('browseItems.html', 
                         items=items, 
                         username=session.get("username"))

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    item = db.execute("""
        SELECT 
            i.id,
            i.name,
            i.description,
            i.category,
            i.condition,
            i.image,
            i.created_at,
            u.username AS owner_name,
            u.phone AS owner_phone,
            u.hostel AS owner_hostel
        FROM items i
        JOIN users u ON i.owner_id = u.id
        WHERE i.id = :item_id
    """, (item_id,)).fetchone()

    if not item:
        return redirect(url_for('browse_items'))

    return render_template('items_detail.html', item=item, username=session.get("username"))

# Upload/Add Item Route
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        category = request.form.get('category')
        description = request.form.get('description')
        condition = request.form.get('condition')
        looking_for = request.form.get('looking_for', '')
        hostel = request.form.get('hostel')
        contact_method = request.form.get('contact_method', 'email')
        
        # Validate required fields
        if not all([name, category, description, condition, hostel]):
            return render_template('Upload.html', 
                                 error="Please fill in all required fields",
                                 username=session.get("username"))
        
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            
            # Check if file was selected
            if file and file.filename != '':
                # Validate file type
                if not allowed_file(file.filename):
                    return render_template('Upload.html', 
                                         error="Invalid file type. Only PNG, JPG, and JPEG are allowed",
                                         username=session.get("username"))
                
                # Secure the filename and make it unique
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                image_filename = f"{timestamp}_{filename}"
                
                # Save the file
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    file.save(file_path)
                except Exception as e:
                    return render_template('Upload.html', 
                                         error=f"Failed to upload image: {str(e)}",
                                         username=session.get("username"))
        
        # Insert into database
        try:
            db = get_db()
            db.execute('''
                INSERT INTO items (
                    owner_id, name, category, description, condition, 
                    looking_for, hostel, contact_method, image, 
                    is_active, views, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, datetime('now'))
            ''', (
                session['user_id'], name, category, description, condition,
                looking_for, hostel, contact_method, image_filename
            ))
            db.commit()
            
            # Redirect to browse page after successful upload
            return redirect(url_for('browse_items'))
            
        except Exception as e:
            # If database insert fails and image was uploaded, delete the image
            if image_filename:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                except:
                    pass
            
            return render_template('Upload.html', 
                                 error=f"Failed to create listing: {str(e)}",
                                 username=session.get("username"))
    
    # GET request - show the form
    return render_template('Upload.html', username=session.get("username"))

# Save item function (for the heart button)
@app.route('/save-item/<int:item_id>', methods=['POST'])
def save_item(item_id):
    if 'user_id' not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    user_id = session['user_id']
    db = get_db()

    item = db.execute("""
        SELECT id, owner_id, is_active
        FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for("browse_items"))

    if item['is_active'] != 1:
        flash("Item not available.", "warning")
        return redirect(url_for("item_detail", item_id=item_id))

    if item['owner_id'] == user_id:
        flash("Cannot save your own item.", "warning")
        return redirect(url_for("browse_items", item_id=item_id))

    existing = db.execute("""
        SELECT 1 FROM saved_items
        WHERE user_id = ? AND item_id = ?
    """, (user_id, item_id)).fetchone()

    if existing:
        flash("Item already saved.", "warning")
        return redirect(url_for("browse_items", item_id=item_id))

    db.execute("""
        INSERT INTO saved_items (user_id, item_id)
        VALUES (?, ?)
    """, (user_id, item_id))
    db.commit()

    flash("Item saved successfully.", "success")
    return redirect(url_for("browse_items", item_id=item_id))





@app.route('/unsave-item/<int:item_id>', methods=['POST'])
def unsave_item(item_id):
    if 'user_id' not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    db = get_db()

    db.execute("""
        DELETE FROM saved_items
        WHERE user_id = ? AND item_id = ?
    """, (session['user_id'], item_id))
    db.commit()

    flash("Item removed from saved items.", "warning")
    return redirect(url_for("profile") + "#saved-items")


@app.route('/notifications')
def notifications():
    return render_template('notifications.html', username=session["username"])



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
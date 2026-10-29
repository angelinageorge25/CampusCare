import os, sqlite3, re
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from collections import Counter

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "campus_tracker.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_BYTES = 4 * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-secret-change-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

CATEGORIES = ["Maintenance", "Classroom", "Water", "Campus Facility", "Other"]
STATUSES = ["Submitted", "In Progress", "Resolved", "Rejected"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def classify(text):
    t = text.lower()
    rules = {
        "Water": ["water", "tap", "drinking", "leak", "pipeline", "washroom"],
        "Classroom": ["classroom", "projector", "bench", "board", "fan", "light", "ac", "air conditioner"],
        "Maintenance": ["repair", "broken", "damage", "electric", "socket", "door", "window"],
        "Campus Facility": ["library", "parking", "hostel", "canteen", "lift", "wifi", "internet", "pathway"]
    }
    for category, words in rules.items():
        if any(w in t for w in words):
            return category
    return "Other"

def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','staff')),
            display_name TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL,
            category TEXT NOT NULL, photo TEXT, status TEXT NOT NULL DEFAULT 'Submitted',
            priority TEXT NOT NULL DEFAULT 'Medium', priority_approved INTEGER NOT NULL DEFAULT 0,
            staff_note TEXT DEFAULT '', student_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id))""")
        users = [
            ("student", "student123", "student", "Demo Student"),
            ("staff", "staff123", "staff", "Demo Staff")
        ]
        for username, password, role, display in users:
            db.execute("INSERT OR IGNORE INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                       (username, generate_password_hash(password), role, display))
        count = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        if count == 0:
            student_id = db.execute("SELECT id FROM users WHERE username='student'").fetchone()[0]
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            samples = [
                ("Leaking water tap near Block B", "Water keeps leaking from the tap outside room 204.", "Water", "In Progress", "High"),
                ("Projector not working", "The projector in classroom C-12 does not turn on.", "Classroom", "Submitted", "Medium"),
                ("Broken pathway light", "The light beside the library entrance is not working.", "Maintenance", "Resolved", "Low"),
                ("Wi-Fi weak in reading hall", "Campus internet is unreliable in the reading hall.", "Campus Facility", "Submitted", "Medium")
            ]
            for title, desc, cat, status, priority in samples:
                db.execute("""INSERT INTO complaints(title,description,category,status,priority,priority_approved,
                           student_id,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?,?)""",
                           (title, desc, cat, status, priority, student_id, now, now))

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def staff_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "staff":
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], username=user["username"],
                           role=user["role"], display_name=user["display_name"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    with connect() as db:
        if session["role"] == "staff":
            tickets = db.execute("""SELECT c.*, u.display_name AS reporter FROM complaints c
                                 JOIN users u ON c.student_id=u.id ORDER BY c.created_at DESC""").fetchall()
            total = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
            open_count = db.execute("SELECT COUNT(*) FROM complaints WHERE status IN ('Submitted','In Progress')").fetchone()[0]
            resolved = db.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
        else:
            tickets = db.execute("SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC",
                                 (session["user_id"],)).fetchall()
            total = db.execute("SELECT COUNT(*) FROM complaints WHERE student_id=?", (session["user_id"],)).fetchone()[0]
            open_count = db.execute("SELECT COUNT(*) FROM complaints WHERE student_id=? AND status IN ('Submitted','In Progress')",
                                    (session["user_id"],)).fetchone()[0]
            resolved = db.execute("SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='Resolved'",
                                  (session["user_id"],)).fetchone()[0]
    return render_template("dashboard.html", tickets=tickets, total=total, open_count=open_count, resolved=resolved)

@app.route("/complaint/new", methods=["GET", "POST"])
@login_required
def new_complaint():
    if session["role"] != "student":
        abort(403)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        supplied_category = request.form.get("category", "AI")
        if len(title) < 4 or len(description) < 8:
            flash("Please enter a descriptive title and issue details.", "warning")
            return render_template("new_complaint.html", categories=CATEGORIES)
        category = classify(title + " " + description) if supplied_category == "AI" else supplied_category
        if category not in CATEGORIES:
            category = "Other"
        photo_name = None
        file = request.files.get("photo")
        if file and file.filename:
            safe = secure_filename(file.filename)
            ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
            if ext not in ALLOWED_EXTENSIONS:
                flash("Photo must be PNG, JPG, JPEG, or WEBP.", "danger")
                return render_template("new_complaint.html", categories=CATEGORIES)
            photo_name = datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + safe
            file.save(os.path.join(UPLOAD_DIR, photo_name))
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with connect() as db:
            db.execute("""INSERT INTO complaints(title,description,category,photo,student_id,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?)""",
                       (title, description, category, photo_name, session["user_id"], now, now))
            ticket_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        flash(f"Complaint #{ticket_id} submitted. Staff can review its priority.", "success")
        return redirect(url_for("dashboard"))
    return render_template("new_complaint.html", categories=CATEGORIES)

@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    with connect() as db:
        ticket = db.execute("""SELECT c.*, u.display_name AS reporter FROM complaints c
                            JOIN users u ON c.student_id=u.id WHERE c.id=?""", (ticket_id,)).fetchone()
    if not ticket:
        abort(404)
    if session["role"] != "staff" and ticket["student_id"] != session["user_id"]:
        abort(403)
    return render_template("ticket_detail.html", ticket=ticket, statuses=STATUSES, priorities=PRIORITIES)

@app.route("/ticket/<int:ticket_id>/update", methods=["POST"])
@staff_required
def update_ticket(ticket_id):
    status = request.form.get("status", "")
    priority = request.form.get("priority", "Medium")
    note = request.form.get("staff_note", "").strip()[:500]
    approved = request.form.get("approve_priority") == "yes"
    if status not in STATUSES or priority not in PRIORITIES:
        flash("Please choose valid status and priority.", "danger")
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with connect() as db:
        exists = db.execute("SELECT id FROM complaints WHERE id=?", (ticket_id,)).fetchone()
        if not exists:
            abort(404)
        db.execute("""UPDATE complaints SET status=?, priority=?, priority_approved=?,
                   staff_note=?, updated_at=? WHERE id=?""",
                   (status, priority, 1 if approved else 0, note, now, ticket_id))
    flash("Ticket updated.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket_id))

@app.route("/insights")
@staff_required
def insights():
    with connect() as db:
        rows = db.execute("SELECT category, title, description, status FROM complaints").fetchall()
    counts = Counter(r["category"] for r in rows)
    repeated = []
    for category, count in counts.most_common():
        examples = [r["title"] for r in rows if r["category"] == category][:3]
        repeated.append({"category": category, "count": count, "examples": examples})
    total = len(rows)
    open_total = sum(r["status"] in ("Submitted", "In Progress") for r in rows)
    summary = (f"There are {total} reports across {len(counts)} categories. "
               f"{open_total} are still open. " +
               ("Most reported: " + counts.most_common(1)[0][0] + "." if counts else "No reports yet."))
    return render_template("insights.html", repeated=repeated, summary=summary, total=total, open_total=open_total)

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to view this page."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="That page or ticket could not be found."), 404

@app.errorhandler(413)
def too_large(e):
    flash("Photo is too large. Maximum size is 4 MB.", "danger")
    return redirect(url_for("new_complaint"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)

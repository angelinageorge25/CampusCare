import os, sqlite3, re
from datetime import datetime
from pathlib import Path
from collections import Counter

import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("CAMPUSCARE_DB", str(BASE_DIR / "campus_tracker.db"))
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
CATEGORIES = ["Maintenance", "Classroom", "Water", "Campus Facility", "Other"]
STATUSES = ["Submitted", "In Progress", "Resolved", "Rejected"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]

st.set_page_config(page_title="CampusCare | Campus Issue Tracker", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#172536;--muted:#68778a;--blue:#3d65e8;--line:#e8edf4}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp{background:#f8faff}.block-container{max-width:1180px;padding-top:2rem;padding-bottom:2rem}
h1,h2,h3,h4,h5{font-family:'Manrope',sans-serif;letter-spacing:-.035em;color:#172536}
[data-testid="stSidebar"]{background:#14243a}[data-testid="stSidebar"] *{color:#fff!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label{background:#20344f;border-radius:10px;padding:9px 12px;margin:3px 0}
.hero{background:linear-gradient(120deg,#f0f4ff 0%,#fff 70%);border:1px solid #e6ecff;border-radius:26px;padding:2.2rem}
.eyebrow{font-size:.72rem;font-weight:800;letter-spacing:.13em;color:#3d65e8;text-transform:uppercase}
.panel,.feature,.stat{background:#fff;border:1px solid #e8edf4;border-radius:18px;padding:20px;box-shadow:0 10px 30px #253b5b08}
.stat-label{font-size:.82rem;color:#68778a;font-weight:600}.stat-value{font-family:'Manrope';font-size:2.1rem;font-weight:800;line-height:1.2;margin-top:5px}
.ticket{background:#fff;border:1px solid #e8edf4;border-radius:16px;padding:18px;margin:10px 0}
.small-muted{color:#68778a;font-size:.9rem}.tag{display:inline-block;background:#eff3ff;color:#455fc1;padding:4px 9px;border-radius:7px;font-size:.75rem;font-weight:700}
.status{display:inline-block;border-radius:30px;padding:5px 10px;font-size:.75rem;font-weight:700}.Submitted{background:#edf1ff;color:#455dbe}.In-Progress{background:#fff3d9;color:#956700}.Resolved{background:#e2f7ed;color:#1d7a53}.Rejected{background:#ffebeb;color:#b54242}
div.stButton>button,div.stFormSubmitButton>button{border-radius:10px;font-weight:700}
.stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]{border-radius:10px}
hr{border-color:#e8edf4}
</style>
""", unsafe_allow_html=True)


def connect():
    db = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
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
        if any(word in t for word in words):
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
        demo_users = [
            ("student", "student123", "student", "Demo Student"),
            ("staff", "staff123", "staff", "Demo Staff")
        ]
        for username, password, role, display in demo_users:
            db.execute("INSERT OR IGNORE INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                       (username, generate_password_hash(password), role, display))
        count = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        if count == 0:
            sid = db.execute("SELECT id FROM users WHERE username='student'").fetchone()[0]
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            samples = [
                ("Leaking water tap near Block B", "Water keeps leaking from the tap outside room 204.", "Water", "In Progress", "High"),
                ("Projector not working", "The projector in classroom C-12 does not turn on.", "Classroom", "Submitted", "Medium"),
                ("Broken pathway light", "The light beside the library entrance is not working.", "Maintenance", "Resolved", "Low"),
                ("Wi-Fi weak in reading hall", "Campus internet is unreliable in the reading hall.", "Campus Facility", "Submitted", "Medium")]
            for title, desc, cat, status, priority in samples:
                db.execute("""INSERT INTO complaints(title,description,category,status,priority,priority_approved,
                           student_id,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?,?)""",
                           (title, desc, cat, status, priority, sid, now, now))


def get_user(username):
    with connect() as db:
        return db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def set_page(page):
    st.session_state.page = page


def login_screen():
    st.markdown('<div class="hero"><div class="eyebrow">A better campus starts with a report</div><h1 style="font-size:3rem;margin:.8rem 0 .3rem">Welcome to <span style="color:#3d65e8">CampusCare</span></h1><p class="small-muted">One simple place to report campus problems, follow updates, and help staff spot recurring issues.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown("### From issue to action")
        for n, title, desc in [("01", "Report it", "Create a categorized ticket and optionally add a photo."), ("02", "Track it", "See status, staff notes, and the latest update."), ("03", "Improve together", "Staff review priorities and identify repeat issues.")]:
            st.markdown(f'<div class="feature" style="margin-bottom:12px"><span class="eyebrow">{n}</span><h3 style="margin:.4rem 0">{title}</h3><span class="small-muted">{desc}</span></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Sign in to continue")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            user = get_user(username.strip())
            if user and check_password_hash(user["password_hash"], password):
                st.session_state.user = {"id": user["id"], "username": user["username"], "role": user["role"], "display_name": user["display_name"]}
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("Invalid username or password.")
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("**Demo accounts**")
        st.info("Student: `student` / `student123`\n\nStaff: `staff` / `staff123`")
        st.markdown('</div>', unsafe_allow_html=True)


def get_tickets(user):
    with connect() as db:
        if user["role"] == "staff":
            rows = db.execute("""SELECT c.*, u.display_name AS reporter FROM complaints c
                               JOIN users u ON c.student_id=u.id ORDER BY c.created_at DESC, c.id DESC""").fetchall()
        else:
            rows = db.execute("SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC, id DESC", (user["id"],)).fetchall()
    return rows


def dashboard(user):
    st.markdown(f"## Good day, {user['display_name']} 👋")
    st.caption("Here is an overview of campus reports and their progress.")
    tickets = get_tickets(user)
    total = len(tickets)
    open_count = sum(t["status"] in ("Submitted", "In Progress") for t in tickets)
    resolved = sum(t["status"] == "Resolved" for t in tickets)
    c1,c2,c3 = st.columns(3)
    for col, label, value in [(c1,"Total reports",total),(c2,"Open reports",open_count),(c3,"Resolved",resolved)]:
        with col: st.markdown(f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value}</div></div>', unsafe_allow_html=True)
    st.markdown("### Recent complaints")
    if not tickets:
        st.info("No complaints have been reported yet.")
    for ticket in tickets:
        with st.container(border=True):
            a,b = st.columns([4,1])
            with a:
                st.markdown(f"**#{ticket['id']} · {ticket['title']}**")
                st.caption(f"{ticket['category']} · Reported {ticket['created_at']}" + (f" · By {ticket['reporter']}" if user['role']=="staff" else ""))
            with b:
                st.markdown(f"`{ticket['status']}`")
                if st.button("View details", key=f"view_{ticket['id']}", use_container_width=True):
                    st.session_state.ticket_id = ticket["id"]
                    st.session_state.page = "Ticket details"
                    st.rerun()


def new_complaint(user):
    st.markdown("## Report a campus issue")
    st.write("Share the details below. Staff will review your report and update its status.")
    with st.form("complaint_form"):
        title = st.text_input("Complaint title", placeholder="e.g. Water tap leaking near Block B")
        description = st.text_area("Describe the issue", height=140, placeholder="Tell us where the issue is and what happened...")
        category_choice = st.selectbox("Category", ["AI - Suggest category"] + CATEGORIES)
        photo = st.file_uploader("Attach a photo (optional, PNG/JPG/WEBP, max 4 MB)", type=["png","jpg","jpeg","webp"])
        submitted = st.form_submit_button("Submit complaint", type="primary", use_container_width=True)
    if submitted:
        if len(title.strip()) < 4 or len(description.strip()) < 8:
            st.warning("Please enter a descriptive title and issue details.")
        elif photo and photo.size > MAX_UPLOAD_BYTES:
            st.error("Photo is too large. Maximum size is 4 MB.")
        else:
            category = classify(title + " " + description) if category_choice.startswith("AI") else category_choice
            photo_name = None
            if photo:
                ext = photo.name.rsplit(".",1)[-1].lower()
                photo_name = datetime.now().strftime("%Y%m%d%H%M%S%f") + "." + ext
                (UPLOAD_DIR / photo_name).write_bytes(photo.getvalue())
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            with connect() as db:
                cur = db.execute("""INSERT INTO complaints(title,description,category,photo,student_id,created_at,updated_at)
                                  VALUES(?,?,?,?,?,?,?)""", (title.strip(),description.strip(),category,photo_name,user["id"],now,now))
                ticket_id = cur.lastrowid
            st.success(f"Complaint #{ticket_id} submitted successfully. Staff can now review it.")
            st.session_state.page = "Dashboard"
            st.rerun()


def ticket_detail(user):
    ticket_id = st.session_state.get("ticket_id")
    with connect() as db:
        ticket = db.execute("""SELECT c.*, u.display_name AS reporter FROM complaints c
                            JOIN users u ON c.student_id=u.id WHERE c.id=?""", (ticket_id,)).fetchone()
    if not ticket:
        st.error("That complaint could not be found."); return
    if user["role"] != "staff" and ticket["student_id"] != user["id"]:
        st.error("You don't have permission to view this complaint."); return
    st.markdown(f"## Complaint #{ticket['id']}")
    st.markdown(f"### {ticket['title']}")
    x,y,z = st.columns(3)
    x.metric("Status", ticket["status"]); y.metric("Category",ticket["category"]); z.metric("Priority",ticket["priority"])
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("**Description**")
    st.write(ticket["description"])
    st.caption(f"Reported by {ticket['reporter']} · {ticket['created_at']} · Last updated {ticket['updated_at']}")
    if ticket["photo"]:
        path = UPLOAD_DIR / ticket["photo"]
        if path.exists(): st.image(str(path), caption="Attached photo", width=500)
    if ticket["staff_note"]:
        st.info("Staff note: " + ticket["staff_note"])
    st.markdown('</div>', unsafe_allow_html=True)
    if user["role"] == "staff":
        st.markdown("### Review and update")
        with st.form(f"update_{ticket_id}"):
            status = st.selectbox("Status", STATUSES, index=STATUSES.index(ticket["status"]))
            priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(ticket["priority"]))
            note = st.text_area("Staff note", value=ticket["staff_note"] or "", max_chars=500)
            approved = st.checkbox("Priority reviewed", value=bool(ticket["priority_approved"]))
            save = st.form_submit_button("Save update", type="primary")
        if save:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            with connect() as db:
                db.execute("UPDATE complaints SET status=?,priority=?,priority_approved=?,staff_note=?,updated_at=? WHERE id=?",
                           (status,priority,1 if approved else 0,note.strip(),now,ticket_id))
            st.success("Complaint updated."); st.rerun()


def insights():
    st.markdown("## Issue insights")
    with connect() as db:
        rows = db.execute("SELECT category,title,description,status FROM complaints").fetchall()
    counts = Counter(r["category"] for r in rows)
    total = len(rows); open_total = sum(r["status"] in ("Submitted","In Progress") for r in rows)
    resolved = sum(r["status"] == "Resolved" for r in rows)
    a,b,c = st.columns(3)
    a.metric("Total reports",total); b.metric("Still open",open_total); c.metric("Resolved",resolved)
    if counts:
        left,right = st.columns([1,1])
        with left:
            st.markdown("### Reports by category")
            st.bar_chart({"Reports":dict(counts)})
        with right:
            st.markdown("### Status overview")
            status_counts = Counter(r["status"] for r in rows)
            st.bar_chart({"Reports":dict(status_counts)})
        st.markdown("### Repeated issue categories")
        for category,count in counts.most_common():
            examples = [r["title"] for r in rows if r["category"]==category][:3]
            with st.container(border=True):
                st.markdown(f"**{category}** · {count} report(s)")
                st.caption("Examples: " + "; ".join(examples))
        most = counts.most_common(1)[0][0]
        st.info(f"There are {total} reports across {len(counts)} categories. {open_total} are still open. Most reported category: {most}.")
    else:
        st.info("No reports yet.")


init_db()

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

user = st.session_state.user
if not user:
    st.markdown("<div style='font-size:1.25rem;font-weight:800;color:#14243a;margin-bottom:1rem'>✦ CampusCare</div>", unsafe_allow_html=True)
    login_screen()
else:
    with st.sidebar:
        st.markdown("# ✦ CampusCare")
        st.caption("Campus issue tracker")
        st.markdown(f"**{user['display_name']}**")
        st.caption(user["role"].title())
        st.divider()
        options = ["Dashboard"]
        if user["role"] == "student": options.append("Report an issue")
        else: options.append("Issue insights")
        if st.session_state.page == "Ticket details": options.append("Ticket details")
        selected = st.radio("Navigation", options, index=options.index(st.session_state.page) if st.session_state.page in options else 0, label_visibility="collapsed")
        st.session_state.page = selected
        st.divider()
        if st.button("Sign out", use_container_width=True):
            st.session_state.user = None
            st.session_state.page = "Dashboard"
            st.session_state.pop("ticket_id", None)
            st.rerun()
    if st.session_state.page == "Dashboard": dashboard(user)
    elif st.session_state.page == "Report an issue": new_complaint(user)
    elif st.session_state.page == "Issue insights" and user["role"] == "staff": insights()
    elif st.session_state.page == "Ticket details": ticket_detail(user)
    st.markdown("<hr><div style='text-align:center;color:#68778a;font-size:.85rem'>CampusCare · A student-first campus issue tracker</div>", unsafe_allow_html=True)

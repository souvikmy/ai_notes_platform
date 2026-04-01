from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, datetime, json, requests

# ── Auto-load .env file if it exists (no extra library needed) ───────────────
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

app = Flask(__name__)
app.secret_key = "ai_notes_secret_key_2024"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ─── DB SETUP ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("notes.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT DEFAULT '',
            avatar_color TEXT DEFAULT '#6C63FF',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            subject TEXT,
            filename TEXT NOT NULL,
            summary TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER NOT NULL,
            UNIQUE(user_id, note_id)
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            UNIQUE(follower_id, following_id)
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()
    db.close()

init_db()

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    db.close()
    return user

def call_claude(messages, system="You are a helpful AI assistant for students."):
    if not ANTHROPIC_API_KEY:
        return "⚠️ Set your ANTHROPIC_API_KEY environment variable to enable AI features."
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": 1000, "system": system, "messages": messages},
            timeout=30
        )
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

def extract_pdf_text(filepath):
    try:
        import PyPDF2
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:10]:
                text += page.extract_text() or ""
        return text[:4000]
    except:
        return ""

# ─── AUTH ROUTES ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", user=current_user())

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.json
        username, email, password = data["username"], data["email"], data["password"]
        colors = ["#6C63FF","#FF6584","#43B89C","#F7B731","#FC5C65","#45AAF2"]
        color = colors[hash(username) % len(colors)]
        db = get_db()
        try:
            db.execute("INSERT INTO users (username,email,password,avatar_color) VALUES (?,?,?,?)",
                       (username, email, generate_password_hash(password), color))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            session["user_id"] = user["id"]
            return jsonify({"success": True})
        except sqlite3.IntegrityError:
            return jsonify({"error": "Username or email already exists"}), 400
        finally:
            db.close()
    return render_template("auth.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (data["username"],)).fetchone()
    db.close()
    if user and check_password_hash(user["password"], data["password"]):
        session["user_id"] = user["id"]
        return jsonify({"success": True})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ─── NOTES ROUTES ─────────────────────────────────────────────────────────────
@app.route("/feed")
def feed():
    if not current_user():
        return redirect("/register")
    return render_template("feed.html", user=current_user())

@app.route("/api/feed")
def api_feed():
    user = current_user()
    db = get_db()
    page = int(request.args.get("page", 1))
    offset = (page - 1) * 12
    search = request.args.get("search", "")
    subject = request.args.get("subject", "")
    query = """
        SELECT n.*, u.username, u.avatar_color,
        (SELECT COUNT(*) FROM likes WHERE note_id=n.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE note_id=n.id) as comment_count,
        (SELECT COUNT(*) FROM likes WHERE note_id=n.id AND user_id=?) as user_liked
        FROM notes n JOIN users u ON n.user_id=u.id
        WHERE (n.title LIKE ? OR n.description LIKE ? OR n.subject LIKE ?)
        {}
        ORDER BY n.created_at DESC LIMIT 12 OFFSET ?
    """.format("AND n.subject=?" if subject else "")
    params = [user["id"] if user else 0, f"%{search}%", f"%{search}%", f"%{search}%"]
    if subject:
        params.append(subject)
    params.append(offset)
    notes = [dict(r) for r in db.execute(query, params).fetchall()]
    db.close()
    return jsonify(notes)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not current_user():
        return redirect("/register")
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file"}), 400
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        # Auto summary
        text = extract_pdf_text(filepath)
        summary = ""
        if text:
            summary = call_claude(
                [{"role": "user", "content": f"Summarize these notes in 3-4 bullet points for students:\n\n{text}"}],
                "You are an expert at summarizing academic notes. Be concise and student-friendly."
            )
        db = get_db()
        db.execute("INSERT INTO notes (user_id,title,description,subject,filename,summary) VALUES (?,?,?,?,?,?)",
                   (current_user()["id"], request.form["title"], request.form.get("description",""),
                    request.form.get("subject","General"), filename, summary))
        db.commit()
        db.close()
        return jsonify({"success": True, "summary": summary})
    return render_template("upload.html", user=current_user())

@app.route("/note/<int:note_id>")
def view_note(note_id):
    db = get_db()
    db.execute("UPDATE notes SET views=views+1 WHERE id=?", (note_id,))
    db.commit()
    note = db.execute("""
        SELECT n.*, u.username, u.avatar_color, u.bio,
        (SELECT COUNT(*) FROM likes WHERE note_id=n.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE note_id=n.id) as comment_count,
        (SELECT COUNT(*) FROM follows WHERE following_id=n.user_id) as follower_count
        FROM notes n JOIN users u ON n.user_id=u.id WHERE n.id=?
    """, (note_id,)).fetchone()
    if not note:
        return "Note not found", 404
    comments = db.execute("""
        SELECT c.*, u.username, u.avatar_color FROM comments c
        JOIN users u ON c.user_id=u.id WHERE c.note_id=? ORDER BY c.created_at DESC
    """, (note_id,)).fetchall()
    db.close()
    return render_template("note.html", note=dict(note), comments=[dict(c) for c in comments], user=current_user())

@app.route("/api/like/<int:note_id>", methods=["POST"])
def like_note(note_id):
    user = current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    db = get_db()
    existing = db.execute("SELECT id FROM likes WHERE user_id=? AND note_id=?", (user["id"], note_id)).fetchone()
    if existing:
        db.execute("DELETE FROM likes WHERE user_id=? AND note_id=?", (user["id"], note_id))
        liked = False
    else:
        db.execute("INSERT INTO likes (user_id,note_id) VALUES (?,?)", (user["id"], note_id))
        liked = True
    db.commit()
    count = db.execute("SELECT COUNT(*) as c FROM likes WHERE note_id=?", (note_id,)).fetchone()["c"]
    db.close()
    return jsonify({"liked": liked, "count": count})

@app.route("/api/comment/<int:note_id>", methods=["POST"])
def add_comment(note_id):
    user = current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    content = request.json.get("content", "").strip()
    if not content:
        return jsonify({"error": "Empty comment"}), 400
    db = get_db()
    db.execute("INSERT INTO comments (user_id,note_id,content) VALUES (?,?,?)", (user["id"], note_id, content))
    db.commit()
    db.close()
    return jsonify({"success": True, "username": user["username"], "avatar_color": user["avatar_color"], "content": content})

@app.route("/api/follow/<int:target_id>", methods=["POST"])
def follow_user(target_id):
    user = current_user()
    if not user or user["id"] == target_id:
        return jsonify({"error": "Invalid"}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM follows WHERE follower_id=? AND following_id=?", (user["id"], target_id)).fetchone()
    if existing:
        db.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (user["id"], target_id))
        following = False
    else:
        db.execute("INSERT INTO follows (follower_id,following_id) VALUES (?,?)", (user["id"], target_id))
        following = True
    db.commit()
    count = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id=?", (target_id,)).fetchone()["c"]
    db.close()
    return jsonify({"following": following, "count": count})

# ─── AI ROUTES ────────────────────────────────────────────────────────────────
@app.route("/api/ai/chat/<int:note_id>", methods=["POST"])
def ai_chat(note_id):
    user = current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    user_msg = request.json.get("message", "")
    db = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    history = db.execute("SELECT role,content FROM chat_history WHERE user_id=? AND note_id=? ORDER BY created_at LIMIT 20",
                         (user["id"], note_id)).fetchall()
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], note["filename"])
    note_text = extract_pdf_text(filepath) if os.path.exists(filepath) else ""
    messages = [{"role": r["role"], "content": r["content"]} for r in history]
    messages.append({"role": "user", "content": user_msg})
    system = f"""You are an AI tutor helping a student understand notes titled "{note['title']}".
Summary: {note['summary']}
Note content (first 3000 chars): {note_text[:3000]}
Answer questions about these notes clearly and helpfully."""
    reply = call_claude(messages, system)
    db.execute("INSERT INTO chat_history (user_id,note_id,role,content) VALUES (?,?,?,?)", (user["id"], note_id, "user", user_msg))
    db.execute("INSERT INTO chat_history (user_id,note_id,role,content) VALUES (?,?,?,?)", (user["id"], note_id, "assistant", reply))
    db.commit()
    db.close()
    return jsonify({"reply": reply})

@app.route("/api/ai/smart-search")
def smart_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    db = get_db()
    notes = db.execute("""
        SELECT n.id, n.title, n.description, n.subject, n.summary, u.username
        FROM notes n JOIN users u ON n.user_id=u.id LIMIT 50
    """).fetchall()
    db.close()
    if not notes:
        return jsonify([])
    notes_text = "\n".join([f"ID:{n['id']} Title:{n['title']} Subject:{n['subject']} Desc:{n['description']}" for n in notes])
    prompt = f"""Given this search query: "{query}"
Find the most relevant notes from this list and return ONLY a JSON array of IDs (max 5), most relevant first:
{notes_text}
Return ONLY valid JSON like: [1, 5, 3]"""
    result = call_claude([{"role": "user", "content": prompt}], "You are a search engine. Return only JSON arrays.")
    try:
        ids = json.loads(result.strip().replace("```json","").replace("```",""))
        filtered = [dict(n) for n in notes if n["id"] in ids]
        return jsonify(filtered)
    except:
        return jsonify([])

@app.route("/profile/<username>")
def profile(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        return "User not found", 404
    notes = db.execute("""
        SELECT n.*, (SELECT COUNT(*) FROM likes WHERE note_id=n.id) as like_count
        FROM notes n WHERE n.user_id=? ORDER BY n.created_at DESC
    """, (user["id"],)).fetchall()
    followers = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id=?", (user["id"],)).fetchone()["c"]
    following = db.execute("SELECT COUNT(*) as c FROM follows WHERE follower_id=?", (user["id"],)).fetchone()["c"]
    is_following = False
    me = current_user()
    if me:
        is_following = bool(db.execute("SELECT id FROM follows WHERE follower_id=? AND following_id=?", (me["id"], user["id"])).fetchone())
    db.close()
    return render_template("profile.html", profile_user=dict(user), notes=[dict(n) for n in notes],
                           followers=followers, following=following, is_following=is_following, user=me)

@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

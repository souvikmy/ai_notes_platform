from flask import Flask, render_template, request, jsonify, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, datetime

app = Flask(__name__)
app.secret_key = "ai_notes_secret_key_2024"

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── DATABASE ─────────────────────────
def get_db():
    conn = sqlite3.connect("notes.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT
    );

    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        description TEXT,
        subject TEXT,
        filename TEXT,
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER,
    user_id INTEGER,
    content TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
    """)
    db.commit()
    db.close()

init_db()






# ─── HELPERS ─────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    db.close()
    return user

# ─── HOME → FEED PAGE ────────────────
@app.route("/")
def index():
    user = current_user()
    if not user:
        return redirect("/login-page")
    return render_template("feed.html", user=user)

# ─── LOGIN PAGE (simple) ─────────────
@app.route("/login-page")
def login_page():
    return render_template("auth.html")   # ← FIXED

# ─── REGISTER ───────────────────────
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    db = get_db()
    try:
        db.execute("INSERT INTO users (username,email,password) VALUES (?,?,?)",
                   (data["username"], data["email"], generate_password_hash(data["password"])))
        db.commit()
        return jsonify({"success": True})
    except:
        return jsonify({"error": "User exists"}), 400
    finally:
        db.close()

# ─── LOGIN ──────────────────────────
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (data["username"],)).fetchone()
    db.close()

    if user and check_password_hash(user["password"], data["password"]):
        session["user_id"] = user["id"]
        return jsonify({"success": True})

    return jsonify({"error": "Invalid login"}), 401

# ─── LOGOUT ─────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")



@app.route("/feed")
def feed():
    user = current_user()

    if not user:
        return redirect("/login-page")

    return render_template("feed.html", user=user)

@app.route("/profile/<username>")
def profile(username):
    user = current_user()

    if not user:
        return redirect("/login-page")

    db = get_db()

    profile_user = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    print("PROFILE USER =", profile_user)

    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY id DESC",
        (profile_user["id"],)
        
    ).fetchall()
    print("NOTES =", len(notes))

    db.close()

    return render_template(
        "profile.html",
        user=user,
        profile_user=profile_user,
        notes=notes
    )

#------- ai search ----------------------------

@app.route("/api/ai-search", methods=["POST"])
def ai_search():
    data = request.get_json()
    query = data.get("query", "").lower()

    db = get_db()

    notes = db.execute("""
       SELECT n.*, u.username
       FROM notes n
       JOIN users u ON n.user_id = u.id
       WHERE LOWER(title) LIKE ?
        OR LOWER(description) LIKE ?
        OR LOWER(subject) LIKE ?
    """, (
        f"%{query}%",
        f"%{query}%",
        f"%{query}%"
    )).fetchall()

    db.close()

    return jsonify([
        dict(note) for note in notes
    ])
    
# ─── API FEED (🔥 IMPORTANT) ─────────
@app.route("/api/feed")
def api_feed():
    db = get_db()
    notes = db.execute("""
        SELECT n.*, u.username
        FROM notes n
        JOIN users u ON n.user_id = u.id
        ORDER BY n.id DESC
    """).fetchall()
    db.close()

    return jsonify([dict(n) for n in notes])

@app.route("/api/like/<int:note_id>", methods=["POST"])
def like_note(note_id):
    return jsonify({
        "success": True,
        "count": 1
    })
    
@app.route("/api/comment/<int:note_id>", methods=["POST"])
def add_comment(note_id):

    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Login required"
        }), 401

    data = request.get_json()
    print("COMMENT DATA =", data)

    text = data.get("text", "").strip()
    print("COMMENT TEXT =", text)

    if not text:
        return jsonify({
            "success": False,
            "error": "Empty comment"
        })

    db = get_db()

    db.execute("""
        INSERT INTO comments (
            note_id,
            user_id,
            content
        )
        VALUES (?, ?, ?)
    """, (
        note_id,
        user['id'],
        text
    ))

    db.commit()
    print("COMMENT SAVED")
    
    db.close()

    return jsonify({
        "success": True
    })

# ─── UPLOAD ─────────────────────────
@app.route("/upload", methods=["GET", "POST"])
def upload():
    user = current_user()

    if not user:
        return redirect("/login-page")

    if request.method == "GET":
        return render_template("upload.html", user=user)

    file = request.files.get("file")
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400

    filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    db = get_db()
    db.execute("INSERT INTO notes (user_id,title,description,subject,filename) VALUES (?,?,?,?,?)",
               (user["id"], request.form["title"], request.form.get("description",""),
                request.form.get("subject","General"), filename))
    db.commit()
    db.close()

    return jsonify({
    "success": True,
    "message": "Note uploaded successfully"
})

# ─── DELETE NOTE (🔥 MATCHES HTML) ───
@app.route("/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    user = current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    db = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()

    if not note:
        db.close()
        return jsonify({"error": "Not found"}), 404

    if note["user_id"] != user["id"]:
        db.close()
        return jsonify({"error": "Unauthorized"}), 403

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], note["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    db.execute("DELETE FROM notes WHERE id=?", (note_id,))
    db.commit()
    db.close()

    return jsonify({"success": True})

# ─── VIEW NOTE ──────────────────────
# ─── VIEW NOTE ──────────────────────
@app.route("/note/<int:note_id>")
def view_note(note_id):
    db = get_db()

    note = db.execute("""
        SELECT n.*, u.username
        FROM notes n
        JOIN users u ON n.user_id = u.id
        WHERE n.id = ?
    """, (note_id,)).fetchone()

    print("Note ID:", note_id)
    print("Result:", note)

    if not note:
        db.close()
        return "Note not found", 404

    comments = db.execute("""
    SELECT c.*, u.username
    FROM comments c
    JOIN users u ON c.user_id = u.id
    WHERE c.note_id = ?
    ORDER BY c.id DESC
""", (note_id,)).fetchall()
    print("COMMENTS =", [dict(c) for c in comments])
    print("COMMENTS COUNT =", len(comments))
    print("COMMENTS =", [dict(c) for c in comments])
    
    db.close()

    return render_template(
        "note.html",
        note=note,
        user=current_user(),
        comments=comments,
    )

# ─── FILE SERVE ─────────────────────
@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ─── RUN ────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)

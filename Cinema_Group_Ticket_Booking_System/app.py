import os
import sqlite3
import threading
import time
import uuid
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cinesync-demo-change-this-key")
DB_PATH = os.path.join(os.path.dirname(__file__), "cinema.db")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")
booking_mutex = threading.Lock()
LOCK_SECONDS = 90
SEAT_PRICE = 180

SEED_MOVIES = [
    ("Interstellar", "Sci-Fi • Adventure", "2h 49m", "8.7", "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg", "A journey beyond the stars."),
    ("The Dark Knight", "Action • Crime", "2h 32m", "9.0", "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg", "A city needs a hero."),
    ("Inception", "Sci-Fi • Thriller", "2h 28m", "8.8", "https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg", "Dreams within dreams."),
    ("Dune: Part Two", "Sci-Fi • Drama", "2h 46m", "8.5", "https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohFlWqjYI6MZx9f5G.jpg", "A journey across Arrakis."),
    ("Spider-Man: Across the Spider-Verse", "Animation • Action", "2h 20m", "8.6", "https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj678.jpg", "Miles Morales swings into a new multiverse adventure."),
    ("The Batman", "Action • Crime", "2h 56m", "7.8", "https://image.tmdb.org/t/p/w500/74xTEgt7R36Fpooo50r9T25onhq.jpg", "A detective story in Gotham City."),
    ("Avengers: Endgame", "Action • Adventure", "3h 01m", "8.4", "https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg", "The heroes unite for one final stand."),
    ("Coco", "Animation • Family", "1h 45m", "8.4", "https://image.tmdb.org/t/p/w500/gGEsBPAijhVUFoiNpgZXqRVWJt2.jpg", "A musical journey celebrating family.")
]

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_seats(db, show_id):
    for row in "ABCDEFGH":
        for col in range(1, 11):
            db.execute("INSERT OR IGNORE INTO seats(show_id, seat_code, status) VALUES(?, ?, 'available')",
                       (show_id, f"{row}{col}"))

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS movies(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, genre TEXT,
            duration TEXT, rating TEXT, poster TEXT, description TEXT
        );
        CREATE TABLE IF NOT EXISTS shows(
            id INTEGER PRIMARY KEY AUTOINCREMENT, movie_id INTEGER NOT NULL,
            theatre TEXT, show_time TEXT,
            FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS seats(
            id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER NOT NULL,
            seat_code TEXT NOT NULL, status TEXT DEFAULT 'available',
            UNIQUE(show_id, seat_code),
            FOREIGN KEY(show_id) REFERENCES shows(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS bookings(
            id TEXT PRIMARY KEY, customer TEXT, show_id INTEGER, seat_count INTEGER,
            total REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(show_id) REFERENCES shows(id)
        );
        CREATE TABLE IF NOT EXISTS booking_details(
            id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id TEXT, show_id INTEGER,
            seat_code TEXT, UNIQUE(show_id, seat_code),
            FOREIGN KEY(booking_id) REFERENCES bookings(id)
        );
        CREATE TABLE IF NOT EXISTS seat_locks(
            show_id INTEGER, seat_code TEXT, token TEXT, expires_at REAL,
            PRIMARY KEY(show_id, seat_code)
        );
        """)
        for movie in SEED_MOVIES:
            exists = db.execute("SELECT id,poster FROM movies WHERE title=?", (movie[0],)).fetchone()
            if not exists:
                db.execute("""INSERT INTO movies(title,genre,duration,rating,poster,description)
                              VALUES(?,?,?,?,?,?)""", movie)
            elif exists["poster"] and " " in exists["poster"]:
                # Repair the malformed Interstellar poster URL in the original starter database.
                db.execute("UPDATE movies SET poster=? WHERE id=?", (movie[4], exists["id"]))
        movie_rows = db.execute("SELECT id FROM movies").fetchall()
        for movie in movie_rows:
            shows = db.execute("SELECT id FROM shows WHERE movie_id=?", (movie["id"],)).fetchall()
            if not shows:
                for theatre, show_time in [("Screen 1", "10:30 AM"), ("Screen 1", "02:30 PM"), ("Screen 2", "06:30 PM")]:
                    cur = db.execute("INSERT INTO shows(movie_id,theatre,show_time) VALUES(?,?,?)",
                                     (movie["id"], theatre, show_time))
                    create_seats(db, cur.lastrowid)
            else:
                for show in shows:
                    create_seats(db, show["id"])
                if len(shows) < 2:
                    cur = db.execute("INSERT INTO shows(movie_id,theatre,show_time) VALUES(?,?,?)",
                                     (movie["id"], "Screen 1", "06:30 PM"))
                    create_seats(db, cur.lastrowid)
        db.commit()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify(ok=False, message="Please sign in to the admin dashboard."), 401
        return fn(*args, **kwargs)
    return wrapper

@app.get("/")
def home():
    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    error = None
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if pin == ADMIN_PIN:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        error = "Incorrect admin PIN. Please try again."
    if not session.get("is_admin"):
        return render_template("admin_login.html", error=error)
    return render_template("admin.html")

@app.post("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin"))

@app.get("/api/movies")
def movies():
    with get_db() as db:
        return jsonify([dict(r) for r in db.execute("SELECT * FROM movies ORDER BY id DESC")])

@app.get("/api/shows/<int:movie_id>")
def shows(movie_id):
    with get_db() as db:
        return jsonify([dict(r) for r in db.execute(
            "SELECT * FROM shows WHERE movie_id=? ORDER BY id", (movie_id,))])

@app.get("/api/seats/<int:show_id>")
def seats(show_id):
    now = time.time()
    with get_db() as db:
        db.execute("DELETE FROM seat_locks WHERE expires_at < ?", (now,))
        rows = db.execute("""
            SELECT s.seat_code,s.status,
            CASE WHEN l.token IS NOT NULL THEN 1 ELSE 0 END AS locked
            FROM seats s LEFT JOIN seat_locks l
            ON s.show_id=l.show_id AND s.seat_code=l.seat_code AND l.expires_at>?
            WHERE s.show_id=? ORDER BY s.seat_code
        """, (now, show_id)).fetchall()
        return jsonify([dict(r) for r in rows])

@app.post("/api/book")
def book():
    data = request.get_json(silent=True) or {}
    customer = (data.get("customer") or "Guest").strip()[:60]
    try:
        show_id = int(data.get("show_id", 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Please choose a valid show."), 400
    requested = list(dict.fromkeys(data.get("seats") or []))
    if not customer or not requested or len(requested) > 10:
        return jsonify(ok=False, message="Enter your name and select 1–10 seats."), 400
    if not all(isinstance(s, str) and len(s) <= 4 for s in requested):
        return jsonify(ok=False, message="Invalid seat selection."), 400

    # Critical section: the mutex protects the complete availability-check and booking sequence.
    with booking_mutex:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            db.execute("DELETE FROM seat_locks WHERE expires_at < ?", (now,))
            placeholders = ",".join("?" for _ in requested)
            found = db.execute(
                f"SELECT seat_code,status FROM seats WHERE show_id=? AND seat_code IN ({placeholders})",
                [show_id] + requested).fetchall()
            if len(found) != len(requested):
                db.rollback()
                return jsonify(ok=False, message="One or more seats do not exist."), 400
            booked = [r["seat_code"] for r in found if r["status"] == "booked"]
            locked = db.execute(
                f"SELECT seat_code FROM seat_locks WHERE show_id=? AND expires_at>? AND seat_code IN ({placeholders})",
                [show_id, now] + requested).fetchall()
            if booked or locked:
                db.rollback()
                conflicts = booked + [r["seat_code"] for r in locked]
                return jsonify(ok=False, message="Some seats are no longer available. Please choose again.",
                               conflicts=conflicts), 409
            token = str(uuid.uuid4())
            expires = now + LOCK_SECONDS
            for seat in requested:
                db.execute("INSERT INTO seat_locks(show_id,seat_code,token,expires_at) VALUES(?,?,?,?)",
                           (show_id, seat, token, expires))
            db.execute(f"UPDATE seats SET status='booked' WHERE show_id=? AND seat_code IN ({placeholders})",
                       [show_id] + requested)
            booking_id = "CIN-" + uuid.uuid4().hex[:8].upper()
            total = len(requested) * SEAT_PRICE
            db.execute("INSERT INTO bookings(id,customer,show_id,seat_count,total) VALUES(?,?,?,?,?)",
                       (booking_id, customer, show_id, len(requested), total))
            for seat in requested:
                db.execute("INSERT INTO booking_details(booking_id,show_id,seat_code) VALUES(?,?,?)",
                           (booking_id, show_id, seat))
            db.execute("DELETE FROM seat_locks WHERE token=?", (token,))
            db.commit()
            return jsonify(ok=True, booking_id=booking_id, seats=requested, total=total,
                           message="Your group booking is confirmed!")
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify(ok=False, message="Booking conflict detected. Refresh the seat layout."), 409
        finally:
            db.close()

@app.get("/api/bookings")
def bookings():
    with get_db() as db:
        rows = db.execute("""SELECT b.id,b.customer,b.seat_count,b.total,b.created_at,
            m.title AS movie, s.theatre, s.show_time,
            GROUP_CONCAT(d.seat_code, ', ') AS seats
            FROM bookings b JOIN booking_details d ON b.id=d.booking_id
            JOIN shows s ON b.show_id=s.id JOIN movies m ON s.movie_id=m.id
            GROUP BY b.id ORDER BY b.created_at DESC LIMIT 30""").fetchall()
        return jsonify([dict(r) for r in rows])

@app.get("/api/admin/overview")
@admin_required
def admin_overview():
    with get_db() as db:
        return jsonify({
            "movie_count": db.execute("SELECT COUNT(*) FROM movies").fetchone()[0],
            "show_count": db.execute("SELECT COUNT(*) FROM shows").fetchone()[0],
            "booking_count": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
            "revenue": db.execute("SELECT COALESCE(SUM(total),0) FROM bookings").fetchone()[0],
            "movies": [dict(r) for r in db.execute("SELECT * FROM movies ORDER BY title")],
            "shows": [dict(r) for r in db.execute("""SELECT s.*,m.title AS movie_title
                FROM shows s JOIN movies m ON s.movie_id=m.id ORDER BY m.title,s.id""")],
            "bookings": [dict(r) for r in db.execute("""SELECT b.*,m.title AS movie_title,
                s.show_time,GROUP_CONCAT(d.seat_code, ', ') AS seats
                FROM bookings b JOIN shows s ON b.show_id=s.id
                JOIN movies m ON s.movie_id=m.id
                LEFT JOIN booking_details d ON d.booking_id=b.id
                GROUP BY b.id ORDER BY b.created_at DESC LIMIT 15""")]
        })

@app.post("/api/admin/movies")
@admin_required
def add_movie():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, message="Movie title is required."), 400
    with get_db() as db:
        cur = db.execute("""INSERT INTO movies(title,genre,duration,rating,poster,description)
            VALUES(?,?,?,?,?,?)""", (
            title[:100], (data.get("genre") or "General")[:80],
            (data.get("duration") or "")[:30], (data.get("rating") or "")[:10],
            (data.get("poster") or "")[:500], (data.get("description") or "")[:500]))
        movie_id = cur.lastrowid
        for theatre, show_time in [("Screen 1", "10:30 AM"), ("Screen 1", "02:30 PM"), ("Screen 2", "06:30 PM")]:
            cur = db.execute("INSERT INTO shows(movie_id,theatre,show_time) VALUES(?,?,?)",
                             (movie_id, theatre, show_time))
            create_seats(db, cur.lastrowid)
        db.commit()
    return jsonify(ok=True, message="Movie added with three sample showtimes.")

@app.put("/api/admin/movies/<int:movie_id>")
@admin_required
def update_movie(movie_id):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, message="Movie title is required."), 400
    with get_db() as db:
        cur = db.execute("""UPDATE movies SET title=?,genre=?,duration=?,rating=?,poster=?,description=?
            WHERE id=?""", (title[:100], (data.get("genre") or "")[:80],
            (data.get("duration") or "")[:30], (data.get("rating") or "")[:10],
            (data.get("poster") or "")[:500], (data.get("description") or "")[:500], movie_id))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(ok=False, message="Movie not found."), 404
    return jsonify(ok=True, message="Movie details updated.")

@app.delete("/api/admin/movies/<int:movie_id>")
@admin_required
def delete_movie(movie_id):
    with get_db() as db:
        linked = db.execute("""SELECT COUNT(*) FROM bookings b JOIN shows s ON b.show_id=s.id
                               WHERE s.movie_id=?""", (movie_id,)).fetchone()[0]
        if linked:
            return jsonify(ok=False, message="This movie has bookings and cannot be deleted from the demo database."), 409
        db.execute("DELETE FROM shows WHERE movie_id=?", (movie_id,))
        cur = db.execute("DELETE FROM movies WHERE id=?", (movie_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(ok=False, message="Movie not found."), 404
    return jsonify(ok=True, message="Movie deleted.")

@app.post("/api/admin/shows")
@admin_required
def add_show():
    data = request.get_json(silent=True) or {}
    try:
        movie_id = int(data.get("movie_id"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Choose a movie."), 400
    theatre = (data.get("theatre") or "Screen 1").strip()[:60]
    show_time = (data.get("show_time") or "").strip()[:30]
    if not show_time:
        return jsonify(ok=False, message="Enter a showtime."), 400
    with get_db() as db:
        if not db.execute("SELECT id FROM movies WHERE id=?", (movie_id,)).fetchone():
            return jsonify(ok=False, message="Movie not found."), 404
        cur = db.execute("INSERT INTO shows(movie_id,theatre,show_time) VALUES(?,?,?)",
                         (movie_id, theatre, show_time))
        create_seats(db, cur.lastrowid)
        db.commit()
    return jsonify(ok=True, message="Showtime added.")

@app.delete("/api/admin/shows/<int:show_id>")
@admin_required
def delete_show(show_id):
    with get_db() as db:
        has_booking = db.execute("SELECT COUNT(*) FROM bookings WHERE show_id=?", (show_id,)).fetchone()[0]
        if has_booking:
            return jsonify(ok=False, message="This show has bookings and cannot be deleted."), 409
        db.execute("DELETE FROM seats WHERE show_id=?", (show_id,))
        db.execute("DELETE FROM seat_locks WHERE show_id=?", (show_id,))
        cur = db.execute("DELETE FROM shows WHERE id=?", (show_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(ok=False, message="Showtime not found."), 404
    return jsonify(ok=True, message="Showtime deleted.")

# Initialize on import so both local Flask and Gunicorn/Render have the tables ready.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)

import os
from flask import Flask, render_template, request, jsonify
import sqlite3, threading, time, uuid
from contextlib import contextmanager

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "cinema.db")
booking_mutex = threading.Lock()
LOCK_SECONDS = 90

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS movies(
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, genre TEXT, duration TEXT,
            rating TEXT, poster TEXT, description TEXT
        );
        CREATE TABLE IF NOT EXISTS shows(
            id INTEGER PRIMARY KEY, movie_id INTEGER, theatre TEXT, show_time TEXT,
            FOREIGN KEY(movie_id) REFERENCES movies(id)
        );
        CREATE TABLE IF NOT EXISTS seats(
            id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER, seat_code TEXT,
            status TEXT DEFAULT 'available',
            UNIQUE(show_id, seat_code),
            FOREIGN KEY(show_id) REFERENCES shows(id)
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
        if db.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0:
            movies = [
              ("Interstellar","Sci-Fi • Adventure","2h 49m","8.7","https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6M xlNBvIx.jpg","A journey beyond the stars."),
              ("The Dark Knight","Action • Crime","2h 32m","9.0","https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg","A city needs a hero."),
              ("Inception","Sci-Fi • Thriller","2h 28m","8.8","https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg","Dreams within dreams."),
              ("Dune: Part Two","Sci-Fi • Drama","2h 46m","8.5","https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohFlWqjYI6MZx9f5G.jpg","A journey across Arrakis.")
            ]
            db.executemany("INSERT INTO movies(title,genre,duration,rating,poster,description) VALUES(?,?,?,?,?,?)", movies)
            for mid in range(1,5):
                db.execute("INSERT INTO shows(movie_id,theatre,show_time) VALUES(?,?,?)",(mid,"Screen 1","06:30 PM"))
                sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                for row in "ABCDEFGH":
                    for col in range(1,11):
                        db.execute("INSERT INTO seats(show_id,seat_code) VALUES(?,?)",(sid,f"{row}{col}"))
        db.commit()

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/movies")
def movies():
    with get_db() as db:
        return jsonify([dict(r) for r in db.execute("SELECT * FROM movies")])

@app.get("/api/shows/<int:movie_id>")
def shows(movie_id):
    with get_db() as db:
        return jsonify([dict(r) for r in db.execute("SELECT * FROM shows WHERE movie_id=?",(movie_id,))])

@app.get("/api/seats/<int:show_id>")
def seats(show_id):
    now = time.time()
    with get_db() as db:
        db.execute("DELETE FROM seat_locks WHERE expires_at < ?",(now,))
        rows = db.execute("""
          SELECT s.seat_code,s.status,l.token IS NOT NULL AS locked
          FROM seats s LEFT JOIN seat_locks l
          ON s.show_id=l.show_id AND s.seat_code=l.seat_code AND l.expires_at>?
          WHERE s.show_id=? ORDER BY s.seat_code
        """,(now,show_id)).fetchall()
        return jsonify([dict(r) for r in rows])

@app.post("/api/book")
def book():
    data = request.get_json(force=True)
    customer = (data.get("customer") or "Guest").strip()[:60]
    show_id = int(data.get("show_id", 0))
    requested = list(dict.fromkeys(data.get("seats") or []))
    if not customer or not requested or len(requested) > 10:
        return jsonify(ok=False,message="Enter your name and select 1–10 seats."),400

    # Critical section: mutex protects the complete check-and-book sequence
    with booking_mutex:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            db.execute("DELETE FROM seat_locks WHERE expires_at < ?",(now,))
            placeholders = ",".join("?" for _ in requested)
            found = db.execute(
                f"SELECT seat_code,status FROM seats WHERE show_id=? AND seat_code IN ({placeholders})",
                [show_id]+requested).fetchall()
            if len(found) != len(requested):
                db.rollback()
                return jsonify(ok=False,message="One or more seats do not exist."),400
            booked = [r["seat_code"] for r in found if r["status"] == "booked"]
            locked = db.execute(
                f"SELECT seat_code FROM seat_locks WHERE show_id=? AND expires_at>? AND seat_code IN ({placeholders})",
                [show_id,now]+requested).fetchall()
            if booked or locked:
                db.rollback()
                return jsonify(ok=False,message="Some seats are no longer available. Please choose again.",conflicts=booked+[r["seat_code"] for r in locked]),409

            token = str(uuid.uuid4())
            expires = now + LOCK_SECONDS
            for seat in requested:
                db.execute("INSERT INTO seat_locks(show_id,seat_code,token,expires_at) VALUES(?,?,?,?)",
                           (show_id,seat,token,expires))
            # Atomic group confirmation: all seats are updated in one transaction.
            db.execute(f"UPDATE seats SET status='booked' WHERE show_id=? AND seat_code IN ({placeholders})",
                       [show_id]+requested)
            booking_id = "CIN-" + uuid.uuid4().hex[:8].upper()
            total = len(requested) * 180
            db.execute("INSERT INTO bookings(id,customer,show_id,seat_count,total) VALUES(?,?,?,?,?)",
                       (booking_id,customer,show_id,len(requested),total))
            for seat in requested:
                db.execute("INSERT INTO booking_details(booking_id,show_id,seat_code) VALUES(?,?,?)",
                           (booking_id,show_id,seat))
            db.execute("DELETE FROM seat_locks WHERE token=?",(token,))
            db.commit()
            return jsonify(ok=True,booking_id=booking_id,seats=requested,total=total,
                           message="Your group booking is confirmed!")
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify(ok=False,message="Booking conflict detected. Refresh the seat layout."),409
        finally:
            db.close()

@app.get("/api/bookings")
def bookings():
    with get_db() as db:
        rows=db.execute("""SELECT b.id,b.customer,b.seat_count,b.total,b.created_at,
                           GROUP_CONCAT(d.seat_code, ', ') seats
                           FROM bookings b JOIN booking_details d ON b.id=d.booking_id
                           GROUP BY b.id ORDER BY b.created_at DESC LIMIT 20""").fetchall()
        return jsonify([dict(r) for r in rows])

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        threaded=True
    )
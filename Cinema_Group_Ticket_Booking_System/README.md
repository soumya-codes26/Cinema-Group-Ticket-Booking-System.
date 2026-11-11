# CineSync — Cinema Group Ticket Booking System

A Flask + SQLite web application demonstrating group seat booking, race conditions, mutex synchronization, critical sections and atomic transactions.

## Features
- Movie catalogue with posters, descriptions, search and genre filtering.
- Admin dashboard to add, edit and delete movies.
- Add and remove multiple cinema showtimes for each movie.
- Automatic creation of 80 seats for every new showtime.
- Group booking for up to 10 seats in one transaction.
- Booking history and an interactive OS concurrency simulation.
- SQLite database initialized automatically.

## Run on Windows / VS Code
1. Extract this ZIP.
2. Open the `Cinema_Group_Ticket_Booking_System` folder in VS Code.
3. Open Terminal in that folder.
4. (Optional) Create a virtual environment:
   `py -m venv .venv`
5. Install packages:
   `py -m pip install -r requirements.txt`
6. Run:
   `py app.py`
7. Open `http://127.0.0.1:5000`.

## Admin dashboard
- Open `http://127.0.0.1:5000/admin`.
- Demo PIN: `1234`.
- Add movies, edit movie details, remove movies that do not have bookings, and add/remove showtimes.
- New movies are created with three sample showtimes. Each showtime receives 80 seats.

For deployment, set the `ADMIN_PIN` environment variable to a private value and set `SECRET_KEY` to a long random value. The default demo PIN is only suitable for classroom demonstration; this basic PIN login is not a production authentication system.

## OS concepts demonstrated
- `booking_mutex` protects the complete availability-check and booking critical section within this Flask process.
- `BEGIN IMMEDIATE` starts a SQLite write transaction, serializing competing writers.
- A group is confirmed in one transaction: either every requested seat is booked or none is.
- A UNIQUE constraint on `(show_id, seat_code)` in `booking_details` provides a final duplicate-booking safeguard.

## Deployment on Render
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Root directory: blank when `app.py` is in the repository root.
- Add environment variables `ADMIN_PIN` and `SECRET_KEY` in Render.
- SQLite files on Render's ephemeral filesystem may not persist across service restarts/redeploys. For long-term hosted use, connect a managed persistent database.

## Demo
Open the website in two browser windows. Choose the same show and try overlapping seats. The first completed transaction succeeds; the other receives an unavailable-seat response.

Note: Python's `threading.Lock` is process-local. For a multi-worker or multi-server production deployment, use database row locks or a shared distributed lock service.

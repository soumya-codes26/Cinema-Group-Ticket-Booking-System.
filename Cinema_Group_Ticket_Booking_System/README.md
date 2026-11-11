# Cinema Group Ticket Booking System

A Flask + SQLite demonstration of race conditions, mutex synchronization, critical sections and atomic group booking.

## Run in VS Code (Windows)
1. Extract the ZIP and open this folder in VS Code.
2. Open Terminal in this folder.
3. Create a virtual environment (optional): `py -m venv .venv`
4. Install dependencies: `py -m pip install -r requirements.txt`
5. Start the application: `py app.py`
6. Open http://127.0.0.1:5000

The SQLite database and sample movie/show/seat data are created automatically on first run.

## OS concepts demonstrated
- `booking_mutex` protects the complete availability-check and booking critical section within this Flask process.
- `BEGIN IMMEDIATE` starts a SQLite write transaction, serializing competing writers.
- A group is confirmed in one transaction: either every requested seat is booked or none is.
- A UNIQUE constraint on `(show_id, seat_code)` in `booking_details` provides a final duplicate-booking safeguard.

## Demo
Open the site in two browser windows. Choose the same show and try overlapping seats from both windows. The first completed transaction succeeds; the other receives an unavailable-seat response after refreshing.

Note: Python's `threading.Lock` is process-local. For a multi-worker or multi-server production deployment, use database row locks or a shared distributed lock service. SQLite's `BEGIN IMMEDIATE` serializes write transactions for this single-machine demo.

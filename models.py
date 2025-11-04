import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'booking.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            transport_type TEXT NOT NULL,
            name TEXT,
            from_place TEXT NOT NULL,
            to_place TEXT NOT NULL,
            date TEXT NOT NULL,
            passenger_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            seat_no TEXT NOT NULL,
            fare REAL NOT NULL,
            status TEXT DEFAULT 'Pending Verification',
            payment_proof_url TEXT,
            qr_code_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admin_count = cursor.fetchone()[0]
    
    if admin_count == 0:
        admin_hash = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ('Admin User', 'admin@booking.com', admin_hash, 'admin')
        )
    
    conn.commit()
    conn.close()

class User:
    @staticmethod
    def create(name, email, password, role='user'):
        conn = get_db()
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, password_hash, role)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    @staticmethod
    def get_by_email(email):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    @staticmethod
    def verify_password(user, password):
        return check_password_hash(user['password_hash'], password)

class Booking:
    @staticmethod
    def create(user_id, transport_type, name, from_place, to_place, date, passenger_name, 
            phone, email, seat_no, fare, payment_proof_url=None, qr_code_url=None):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO bookings (user_id, transport_type, name, from_place, to_place, date, 
            passenger_name, phone, email, seat_no, fare, payment_proof_url, qr_code_url) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, transport_type, name, from_place, to_place, date, passenger_name, 
            phone, email, seat_no, fare, payment_proof_url, qr_code_url)
        )
        conn.commit()
        booking_id = cursor.lastrowid
        conn.close()
        return booking_id

    
    @staticmethod
    def get_by_id(booking_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        booking = cursor.fetchone()
        conn.close()
        return dict(booking) if booking else None
    
    @staticmethod
    def get_by_user(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        bookings = cursor.fetchall()
        conn.close()
        return [dict(booking) for booking in bookings]
    
    @staticmethod
    def get_all():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, u.name as user_name, u.email as user_email 
            FROM bookings b 
            JOIN users u ON b.user_id = u.id 
            ORDER BY b.created_at DESC
        ''')
        bookings = cursor.fetchall()
        conn.close()
        return [dict(booking) for booking in bookings]
    
    @staticmethod
    def update_status(booking_id, status):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_payment_proof(booking_id, payment_proof_url):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET payment_proof_url = ? WHERE id = ?", 
                      (payment_proof_url, booking_id))
        conn.commit()
        conn.close()

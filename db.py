import sqlite3

DB_PATH = "database.db"  # adjust path if needed

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
